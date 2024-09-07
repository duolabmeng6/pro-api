import asyncio
import os
import httpx
from typing import Dict, Any, AsyncGenerator, Tuple
from fastapi import HTTPException
from app.provider.models import RequestModel, Message
import ujson as json
from app.log import logger
from app.provider.openaiSSEHandler import openaiSSEHandler



class openaiProvider:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "*/*",
                "User-Agent": "curl/7.68.0",

            },
            timeout=httpx.Timeout(connect=15.0, read=600, write=30.0, pool=30.0),
            # http2=False,  # 将 http2 设置为 False
            # verify=False,
            # follow_redirects=True,
            #
            # proxies={  # 使用字典形式来指定不同类型的代理
            #     "http://": "http://127.0.0.1:8888",
            #     "https://": "http://127.0.0.1:8888",  # 如果代理服务器支持 HTTP 和 HTTPS，则可以这样设置
            # },
        )
        self.DataHeadler = openaiSSEHandler

        self._debug = True
        self._cache = True
        self.setDebugSave("openai")

    def setDebugSave(self, name="openai"):
        name = name.replace("/", "-")
        # 获取当前脚本所在的目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构造文件的绝对路径
        self._debugfile_sse = os.path.join(current_dir + f"/debugdata/{name}_sse.txt")
        self._debugfile_data = os.path.join(current_dir + f"/debugdata/{name}_data.txt")

    async def _get_api_data(self, stream: bool, url: str, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        if stream:
            async with self.client.stream("POST", url, json=payload) as response:
                await self.raise_for_status(response)
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line.startswith('data:'):  # 只处理 SSE 数据行
                            yield line
                yield "[DONE]"
        else:
            # Non-streamed request
            response = await self.client.post(url, headers={
                "Content-Type": "application/json",
                "authorization": f"Bearer {self.api_key}",
            }, json=payload)
            await self.raise_for_status(response)
            response_text = response.content.decode("utf-8")
            yield response_text

    async def sendChatCompletions(self, request: RequestModel) -> AsyncGenerator[str, None]:
        logger.name = f"openaiProvider.{request.id}.request.model"
        payload = await self.get_payload(request)

        url = f"{self.base_url}/chat/completions"
        logger.info(f"\r\nsend {url} \r\nbody:\r\n{json.dumps(payload, indent=2, ensure_ascii=False)}")

        # 调试部分 不要看
        debug_file = self._debugfile_sse if request.stream else self._debugfile_data
        if self._debug:
            error = False
            if self._cache:
                try:
                    if request.stream:
                        with open(debug_file, "r") as f:
                            for line in f:
                                line = line.strip()
                                if line != "":
                                    yield line
                                    error = True
                        return
                    else:
                        with open(debug_file, "r") as f:
                            data = f.read()
                            if data != "":
                                yield data
                                error = True

                except FileNotFoundError:
                    error = False
                    logger.warning(f"Debug file {debug_file} not found, it will be created in write mode.")
            if error:
                return

        file_handle = None
        if self._cache:
            mode = 'w' if request.stream else 'a'
            # 清空文件
            try:
                file_handle = open(debug_file, mode)
            except IOError as e:
                logger.error(f"Unable to open debug file {debug_file}: {e}")

        try:
            # 这里是真正的写的部分
            async for line in self._get_api_data(request.stream, url, payload):
                if self._cache:
                    try:
                        file_handle.write(line + "\n")
                    except IOError as e:
                        logger.error(f"Error writing to debug file: {e}")
                logger.info(f"收到数据\r\n{line}")
                yield line


        finally:
            # Ensure file closure
            if file_handle:
                try:
                    file_handle.close()
                except IOError as e:
                    logger.error(f"Error closing debug file: {e}")

    async def chat2api(self, request: RequestModel, request_model_name: str = "", id: str = "") -> AsyncGenerator[
        str, None]:

        try:
            genData = self.sendChatCompletions(request)
            first_chunk = await genData.__anext__()
        except Exception as e:
            raise HTTPException(status_code=404, detail=e)

        self.DataHeadler = openaiSSEHandler(id, request_model_name)
        if not request.stream:
            content = self.DataHeadler.handle_data_line(first_chunk)
            yield content
            stats_data = self.DataHeadler.get_stats()
            logger.info(f"SSE 数据流迭代完成，统计信息：{stats_data}")
            return

        # 流处理的代码
        yield True
        yield "data: " + self.DataHeadler.generate_sse_response(None)
        content = self.DataHeadler.handle_SSE_data_line(first_chunk)
        if content:
            yield "data: " + content
        async for chunk in genData:
            content = self.DataHeadler.handle_SSE_data_line(chunk)
            if content == "[DONE]":
                yield "data: [DONE]"
                break
            if content:
                yield "data: " + content
        stats_data = self.DataHeadler.get_stats()
        logger.info(f"SSE 数据流迭代完成，统计信息：{stats_data}")
        # logger.info(f"转换为普通：{handler.generate_response()}")



    async def raise_for_status(self, response: httpx.Response):
        if response.status_code == 200:
            return
        response_content = await response.aread()
        error_data = {
            "error": "上游服务器出现错误",
            "response_body": response_content.decode("utf-8"),
            "status_code": response.status_code
        }
        raise HTTPException(status_code=500, detail=error_data)


    async def get_payload(self, request: RequestModel) -> Dict[str, Any]:
        messages = []
        for msg in request.messages:
            tool_calls = getattr(msg, 'tool_calls', None)
            tool_call_id = getattr(msg, 'tool_call_id', None)

            if isinstance(msg.content, list):
                content = []
                for item in msg.content:
                    if item.type == "text":
                        text_message = {"type": "text", "text": item.text}
                        content.append(text_message)
                    elif item.type == "image_url":
                        image_message = {
                            "type": "image_url",
                            "image_url": {
                                "url": item.image_url.url,
                            }
                        }
                        content.append(image_message)
            else:
                content = msg.content

            if tool_calls:
                tool_calls_list = []
                for tool_call in tool_calls:
                    tool_calls_list.append({
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    })
                messages.append({"role": msg.role, "tool_calls": tool_calls_list})
            elif tool_call_id:
                messages.append({"role": msg.role, "tool_call_id": tool_call_id, "content": content})
            else:
                messages.append({"role": msg.role, "content": content})

        payload = {
            "model": request.model,
            "messages": messages,
            "stream": request.stream,
            # "logprobs": True
        }

        for field, value in request.model_dump(exclude_unset=True).items():
            if field not in ['model', 'messages', 'stream'] and value is not None:
                payload[field] = value

        # 如果存在最追踪用的id就删除
        if "id" in payload:
            del payload["id"]

        return payload


if __name__ == "__main__":
    async def main():
        from app.database import Database
        db = Database("../api.yaml")
        model_test = [
             "glm-4-flash",
             "doubao-pro-128k",
             "moonshot-v1-128k",
             "qwen2-72b",
             "deepseek-coder"
        ]
        for model_name in model_test:
            providers, error = await db.get_user_provider("sk-111111", model_name)
            provider = providers[0]
            api_key = provider['api_key']
            base_url = provider['base_url']
            model_name = provider['mapped_model']
            # print(provider)
            print("正在测试", model_name)
            openai_interface = openaiProvider(api_key, base_url)
            openai_interface.setDebugSave(f"{model_name}_{provider['provider']}")
            openai_interface._debug = True
            openai_interface._cache = True

            content = ""
            async for response in openai_interface.chat2api(RequestModel(
                    model=model_name,
                    messages=[Message(role="user", content="请用三句话描述春天。")],
                    stream=True,
            )):
                # content += response
                # logger.info( response)
                logger.info(response)


    asyncio.run(main())
