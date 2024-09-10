import asyncio
from typing import AsyncGenerator
from fastapi import HTTPException
from app.provider.baseProvider import baseProvider
from app.log import logger
from app.provider.gemini.geminiSSEHandler import geminiSSEHandler as SSEHandler
from app.provider.openaiSendBodyHeandler import openaiSendBodyHeandler


class geminiProvider(baseProvider):
    def __init__(self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com/v1beta"):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url
        self.setDebugSave("openai")
        self.DataHeadler = SSEHandler


    async def chat2api(self, request, request_model_name: str = "", id: str = "") -> AsyncGenerator[
        str, None]:
        model = request.get('model', "")
        logger.name = f"geminiProvider.{id}.model.{model}"

        sendReady = openaiSendBodyHeandler(self.api_key, self.base_url, model)
        sendReady.header_openai(request)
        pushdata = sendReady.get_Gemini()  # 改这里

        try:
            genData = self.sendChatCompletions(pushdata)
            first_chunk = await genData.__anext__()
        except Exception as e:
            logger.error("报错了chat2api %s", e)
            raise HTTPException(status_code=404, detail=e)

        self.DataHeadler = SSEHandler(id, request_model_name)
        if not request.get("stream", False):
            content = self.DataHeadler.handle_data_line(first_chunk)
            yield content
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

if __name__ == "__main__":
    async def main():
        from app.apiDB import apiDB
        db = apiDB("../../api.yaml")
        providers, error = db.get_user_provider("sk-111111", "gemini-1.5-flash")
        provider = providers[0]
        print(provider)
        interface = geminiProvider(provider['api_key'], provider['base_url'])
        interface.setDebugSave("weather-geminia_" + provider['mapped_model'])
        interface._debug = True
        interface._cache = True
        model_name = provider['mapped_model']
        # 读取JSON文件
        async for response in interface.chat2api({
            "model": model_name,
            "messages": [{"role": "user", "content": "请用三句话描述春天。"}],
            "stream": False,
        }):
            print(response)


    asyncio.run(main())
