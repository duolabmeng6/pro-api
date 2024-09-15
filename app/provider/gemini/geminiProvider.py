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
        logger.name = f"openaiProvider.{id}.model.{model}"
        sendReady = openaiSendBodyHeandler(self.api_key, self.base_url, model)
        sendReady.header_openai(request)
        pushdata = sendReady.get_Gemini()  # 改这里
        self.DataHeadler = SSEHandler(id, request_model_name)
        async for chunk in self.chat2api_super(request, model, id, pushdata):
            yield chunk


if __name__ == "__main__":
    async def main():
        from app.api_data import db
        import json
        import pyefun
        providers, error = db.get_admin_provider("gemini-1.5-pro")
        provider = providers[0]
        print(provider)
        api_key = provider['api_key']
        base_url = provider['base_url']
        # base_url = "https://gemini.rongyiapi.com/v1beta"
        # interface = geminiProvider(provider['api_key'], provider['base_url'])
        interface = geminiProvider(api_key, base_url)
        interface.setDebugSave("weather-geminia_" + provider['mapped_model'])
        # interface._debug = True
        # interface._cache = True
        model_name = provider['mapped_model']


        djson = pyefun.读入文本("../自留测试数据/xhy的.txt")
        djson = json.loads(djson)

        async for response in interface.chat2api(djson):
            print(response)


        # 读取JSON文件
        # async for response in interface.chat2api({
        #     "model": model_name,
        #     "messages": [{"role": "user", "content": "请用三句话描述春天。"}],
        #     "stream": True,
        # }):
        #     print(response)


    asyncio.run(main())
