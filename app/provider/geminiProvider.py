import asyncio
import httpx
from typing import Dict, Any, AsyncGenerator, Tuple
from fastapi import HTTPException
from app.provider.models import RequestModel, Message
import ujson as json
from app.help import generate_sse_response, build_openai_response
from app.log import logger


class geminiProvider:
    def __init__(self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com/v1beta"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(connect=15.0, read=600, write=30.0, pool=30.0),
            http2=True,
            verify=True,
            follow_redirects=True,
        )
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    async def sendChatCompletions(self, request: RequestModel) -> AsyncGenerator[str, None]:
        logger.name = f"geminiProvider.{request.id}.request.model"
        payload = await get_gemini_payload(request)

        url = f"{self.base_url}/models/{request.model}:generateContent?key={self.api_key}"
        logger.info(f"\r\n发送请求到 {url} \r\n请求体:\r\n{json.dumps(payload, indent=2, ensure_ascii=False)}")

        if request.stream:
            async with self.client.stream("POST", url, json=payload) as response:
                await self.raise_for_status(response)
                async for chunk in response.aiter_text():
                    yield chunk
                    logger.info(f"收到数据\r\n{chunk}")
        else:
            response = await self.client.post(url, json=payload)
            await self.raise_for_status(response)
            data = response.json()
            logger.info(f"收到数据\r\n{json.dumps(data, indent=2, ensure_ascii=False)}")
            yield json.dumps(data)

    async def chat2api(self, request: RequestModel, request_model_name: str = "", id: str = "") -> AsyncGenerator[
        str, None]:
        try:
            genData = self.sendChatCompletions(request)
            first_chunk = await genData.__anext__()
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))

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

    async def extract_content_stream(self, chunk: str) -> Dict[str, Any]:
        try:
            data = json.loads(chunk)
            content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

            if "finishReason" in data.get("candidates", [{}])[0]:
                finish_reason = data["candidates"][0]["finishReason"]
                if finish_reason == "STOP":
                    return {
                        "type": "stop",
                        "content": content,
                        "prompt_tokens": self.prompt_tokens,
                        "completion_tokens": self.completion_tokens,
                        "total_tokens": self.total_tokens
                    }

            return {"type": "content", "content": content}
        except json.JSONDecodeError:
            logger.error(f"JSON解析错误,数据行: {chunk}")
            return {"type": "error", "content": "JSON解析错误"}

    async def extract_content(self, data: str) -> str:
        try:
            parsed_data = json.loads(data)
            content = parsed_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return content
        except json.JSONDecodeError:
            logger.error(f"JSON解析错误,数据: {data}")
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


async def get_gemini_payload(request: RequestModel) -> Dict[str, Any]:
    contents = []
    for msg in request.messages:
        if isinstance(msg.content, list):
            parts = []
            for item in msg.content:
                if item.type == "text":
                    parts.append({"text": item.text})
                elif item.type == "image_url":
                    parts.append({
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": item.image_url.url.split(",")[1]  # 假设base64编码的图片数据
                        }
                    })
            contents.append({"role": msg.role, "parts": parts})
        else:
            contents.append({"role": msg.role, "parts": [{"text": msg.content}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": request.temperature or 0.7,
            "top_p": request.top_p or 0.95,
            "top_k": request.top_k or 40,
            "max_output_tokens": request.max_tokens or 8192,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    }

    return payload


if __name__ == "__main__":
    async def main():
        from app.database import Database
        db = Database("../api.yaml")
        providers, error = await db.get_user_provider("sk-111111", "gemini-1.5-flash")
        print(providers)
        provider = providers[0]
        openai_interface = geminiProvider(provider['api_key'], provider['base_url'])
        # 转api
        # async for response in openai_interface.chat2api(RequestModel(
        #     model="glm-4-flash",
        #     messages=[Message(role="user", content="你好")],
        #     stream=True,
        # )):
        #     print(response)
        #
        async for response in openai_interface.chat(RequestModel(
                model="gemini-1.5-flash",
                messages=[Message(role="user", content="请用三句话描述春天。")],
                stream=True,
        )):
            print(response)

asyncio.run(main())
