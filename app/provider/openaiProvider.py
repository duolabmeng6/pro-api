import asyncio
import httpx
from typing import Dict, Any, AsyncGenerator, Tuple
from fastapi import HTTPException
from app.provider.models import RequestModel, Message
import ujson as json
from app.help import generate_sse_response, build_openai_response
from app.log import logger


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

    async def sendChatCompletions(self, request: RequestModel) -> AsyncGenerator[str, None]:
        logger.name = f"openaiProvider.{request.id}.request.model"
        payload = await get_gpt_payload(request)

        url = f"{self.base_url}/chat/completions"
        logger.info(f"\r\nsend {url} \r\nbody:\r\n{json.dumps(payload, indent=2, ensure_ascii=False)}")

        if request.stream:
            async with self.client.stream("POST", url, json=payload) as response:
                await self.raise_for_status(response)
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if line:
                            yield line
                            logger.info(f"收到数据\r\n{line}")

        if not request.stream:
            response = await self.client.post(url, json=payload)
            await self.raise_for_status(response)
            data = response.json()
            # 我想记录data写到日志
            logger.info(f"收到数据\r\n{json.dumps(data, indent=2, ensure_ascii=False)}")
            yield data

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
        except json.JSONDecodeError:
            # 记录JSON解析错误
            logger.error(f"JSON decode error for line: {line}")
            return {"type": "error", "content": "JSON decode error"}

    async def extract_content(self, data: str) -> str:
        try:
            content = data["choices"][0]["message"]["content"]
            return content
        except json.JSONDecodeError:
            logger.error(f"JSON decode error for line: {data}")
            return ""

    async def extract_usage(self, data: str) -> Tuple[int, int, int]:
        try:
            usage = data.get("usage", {})
            self.prompt_tokens = usage.get("prompt_tokens", 0)
            self.completion_tokens = usage.get("completion_tokens", 0)
            self.total_tokens = usage.get("total_tokens", 0)
            return self.prompt_tokens, self.completion_tokens, self.total_tokens
        except Exception as e:
            logger.error(f"JSON 解析错误，数据行：{data}")
            return 0, 0, 0


async def get_text_message(message: str) -> Dict[str, str]:
    return {"type": "text", "text": message}


async def get_image_message(base64_image: str) -> Dict[str, Any]:
    return {
        "type": "image_url",
        "image_url": {
            "url": base64_image,
        }
    }


async def get_gpt_payload(request: RequestModel) -> Dict[str, Any]:
    messages = []
    for msg in request.messages:
        tool_calls = getattr(msg, 'tool_calls', None)
        tool_call_id = getattr(msg, 'tool_call_id', None)

        if isinstance(msg.content, list):
            content = []
            for item in msg.content:
                if item.type == "text":
                    text_message = await get_text_message(item.text)
                    content.append(text_message)
                elif item.type == "image_url":
                    image_message = await get_image_message(item.image_url.url)
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
        print(providers)
        provider = providers[0]
        openai_interface = openaiProvider(provider['api_key'], provider['base_url'])
        # 转api
        # async for response in openai_interface.chat2api(RequestModel(
        #     model="glm-4-flash",
        #     messages=[Message(role="user", content="你好")],
        #     stream=True,
        # )):
        #     print(response)
        #
        async for response in openai_interface.chat(RequestModel(
                model="glm-4-flash",
                messages=[Message(role="user", content="请用三句话描述春天。")],
                stream=False,
        )):
            print(response)

asyncio.run(main())
