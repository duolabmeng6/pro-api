import asyncio
import httpx
from typing import List, Dict, Any, AsyncGenerator
from app.provider.models import RequestModel, Message, ContentItem, Tool, FunctionParameter, Function
import json
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAiInterface:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "*/*",
                "User-Agent": "curl/7.68.0",  # 模拟 curl 的 User-Agent
            },
            timeout=httpx.Timeout(connect=15.0, read=600, write=30.0, pool=30.0),
            http2=False,  # 将 http2 设置为 False
            verify=True,
            follow_redirects=True,
        )

    async def chat(self, request: RequestModel) -> AsyncGenerator[str, None]:
        long_text = "这是一个很长的文本,用来模拟AI的回复。" * 20

        if request.stream:
            chunk_size = len(long_text) // 5
            for i in range(5):
                start = i * chunk_size
                end = start + chunk_size if i < 4 else None
                yield f"hello\n{long_text[start:end]}"
        else:
            yield long_text



if __name__ == "__main__":
    async def main():
        api_key = "xxxxx"
        base_url = "https://open.bigmodel.cn/api/paas/v4"
        openai_interface = OpenAiInterface(api_key, base_url)
        request = RequestModel(
            model="glm-4-flash",
            messages=[Message(role="user", content="今天的天气")],
            stream=True,
        )
        logger.info("测试流式返回")
        async for response in openai_interface.chat(request):
            logger.info(response)

        logger.info("正常返回")
        request.stream = False
        async for response in openai_interface.chat(request):
            logger.info(response)
    asyncio.run(main())