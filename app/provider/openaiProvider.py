import asyncio
import uuid
from logging import DEBUG

import httpx
from typing import Dict, Any, AsyncGenerator, Tuple
from fastapi import HTTPException
from app.provider.models import RequestModel, Message
import ujson as json
from app.help import generate_sse_response, build_openai_response
from app.log import logger

import pyefun

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
            http2=False,  # 将 http2 设置为 False
            verify=True,
            follow_redirects=True,
        )
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

        self._debugfile_sse = "./debugdata/zpqydata_sse.txt"
        self._debugfile_data = "./debugdata/zpqydata_data.txt"
        self._debugfile_write = False
        self._debug = True

    async def _get_api_data(self, stream: bool, url: str, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        if stream:
            # Streamed request
            async with self.client.stream("POST", url, json=payload) as response:
                await self.raise_for_status(response)
                async for chunk in response.aiter_text():
                    chunk = chunk.strip()
                    if chunk:  # Ignore empty chunks
                        yield chunk
        else:
            # Non-streamed request
            response = await self.client.post(url, json=payload)
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
            try:
                with open(debug_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            yield line
                if not self._debugfile_write:
                    return
            except FileNotFoundError:
                logger.warning(f"Debug file {debug_file} not found, it will be created in write mode.")

        # Prepare to write to debug file if enabled
        file_handle = None
        if self._debugfile_write:
            mode = 'w' if request.stream else 'a'
            try:
                file_handle = open(debug_file, mode)
            except IOError as e:
                logger.error(f"Unable to open debug file {debug_file}: {e}")

        try:
            # 这里是真正的写的部分
            async for line in self._get_api_data(request.stream, url, payload):
                if self._debugfile_write and file_handle:
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

        if not request.stream:
            content = await self.extract_content(first_chunk)
            await self.extract_usage(first_chunk)

            yield await build_openai_response(id, content, request_model_name, self.prompt_tokens,
                                              self.completion_tokens, self.total_tokens)

            return

        # 流处理的代码
        yield True
        yield await generate_sse_response(id, request_model_name)
        content = await self.extract_content_stream(first_chunk)
        yield await generate_sse_response(id, request_model_name, content=content)
        async for chunk in genData:
            content = await self.extract_content_stream(chunk)
            if isinstance(content, dict):
                if "error" in content:
                    logger.error(f"发生错误: {content['error']}")
                    continue

            yield await generate_sse_response(id, request_model_name, content=content)

    async def chat(self, request: RequestModel) -> AsyncGenerator[str, None]:
        try:
            async for chunk in self.sendChatCompletions(request):
                if request.stream:
                    content = await self.extract_content_stream(chunk)
                    if content['type'] == 'content':
                        yield content['content']
                    elif content['type'] == 'stop':
                        break
                else:
                    content = await self.extract_content(chunk)
                    yield content
                    break
        except Exception as e:
            logger.error(f"聊天过程中发生错误: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

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

    async def extract_content_stream(self, line: str) -> Dict[str, Any]:
        """
        解析SSE流数据行提取
        :param line: 数据行
        :return: 解析后的数据

        解析后的数据类型
        {"type": "content", "content": "你好"} # 内容
        {"type": "error", "content": ""} # 不返回就行
        {"type": "function_call", "function": {"name": "function_name", "arguments": "function_arguments"}} # 工具调用
        {"type": "stop", "content": "你好", "prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20} # 完成
        {"type": "end", "content": "[DONE]"} # 结束
        """
        # 初始化数据变量
        data = ""
        # 处理不同格式的数据行
        if line.startswith("data: "):
            data = line[6:]
        elif line.startswith("data:"):
            data = line[5:]

        # 检查是否为结束标记
        if data.strip() == "[DONE]":
            return {"type": "end", "content": "[DONE]"}
        if data == "":
            return {"type": "error", "content": "JSON decode error"}

        try:
            # 解析JSON数据
            data = json.loads(data)
            delta = data["choices"][0]["delta"]
            content = delta.get("content", "")

            # 检查是否有完成原因
            if "finish_reason" in data["choices"][0]:
                finish_reason = data["choices"][0]["finish_reason"]
                if finish_reason == "stop":
                    # 如果完成原因是"stop"，返回包含使用情况的字典
                    usage = data.get("usage", {})
                    self.prompt_tokens = usage.get("prompt_tokens", 0)
                    self.completion_tokens = usage.get("completion_tokens", 0)
                    self.total_tokens = usage.get("total_tokens", 0)
                    return {
                        "type": "stop",
                        "content": content,
                        "prompt_tokens": self.prompt_tokens,
                        "completion_tokens": self.completion_tokens,
                        "total_tokens": self.total_tokens
                    }

            # 处理工具调用
            if not content and "tool_calls" in delta:
                content = json.dumps(delta["tool_calls"])

            # 返回内容
            return {"type": "content", "content": content}
        except Exception as e:
            # 记录JSON解析错误
            logger.error(f"JSON decode error for line data:\r\n{data} \r\nerror:\r\n{e}")

            return {"type": "error", "content": "JSON decode error"}

    async def extract_content(self, data: str) -> str:
        try:
            if isinstance(data, str):
                data = json.loads(data)
            content = data["choices"][0]["message"]["content"]
            return content
        except json.JSONDecodeError:
            logger.error(f"JSON decode error for line: {data}")
            return ""

    async def extract_usage(self, data: str) -> Tuple[int, int, int]:
        try:
            if isinstance(data, str):
                data = json.loads(data)
            usage = data.get("usage", {})
            self.prompt_tokens = usage.get("prompt_tokens", 0)
            self.completion_tokens = usage.get("completion_tokens", 0)
            self.total_tokens = usage.get("total_tokens", 0)
            return self.prompt_tokens, self.completion_tokens, self.total_tokens
        except Exception as e:
            logger.error(f"JSON 解析错误，数据行：{data}")
            return 0, 0, 0




    async def get_payload(self,request: RequestModel) -> Dict[str, Any]:
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
        providers, error = await db.get_user_provider("sk-111111", "glm-4-flash")
        provider = providers[0]
        api_key = provider['api_key']
        base_url = provider['base_url']
        print(provider)
        openai_interface = openaiProvider(api_key, base_url)
        openai_interface._debugfile_sse = "./debugdata/zpqydata_sse.txt"
        openai_interface._debugfile_data = "./debugdata/zpqydata_data.txt"
        openai_interface._debugfile_write = False
        openai_interface._debug = True
        # async for response in openai_interface.chat2api(RequestModel(
        #     model="glm-4-flash",
        #     messages=[Message(role="user", content="你好")],
        #     stream=True,
        # )):
        #     if isinstance(response, bool):
        #         continue
        #     if isinstance(response, str):
        #         logger.info(response)
        #     else:
        #         logger.error(response)


        content = ""
        async for response in openai_interface.chat(RequestModel(
                model="glm-4-flash",
                messages=[Message(role="user", content="请用三句话描述春天。")],
                stream=True,
        )):
            content += response
            logger.info(content)

    asyncio.run(main())
