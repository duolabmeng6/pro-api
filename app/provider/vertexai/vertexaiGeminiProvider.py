
import asyncio
import json
from typing import AsyncGenerator
from http.client import HTTPException

import pyefun

from app.log import logger, error_handling
from app.provider.gemini.geminiSSEHandler import geminiSSEHandler as SSEHandler
from app.provider.openaiSendBodyHeandler import openaiSendBodyHeandler
from app.provider.baseProvider import baseProvider


class vertexaiGeminiProvider(baseProvider):
    def __init__(self,
                 PROJECT_ID,
                 CLIENT_ID,
                 CLIENT_SECRET,
                 REFRESH_TOKEN,
                 ):
        super().__init__()

        self.PROJECT_ID = PROJECT_ID
        self.CLIENT_ID = CLIENT_ID
        self.CLIENT_SECRET = CLIENT_SECRET
        self.REFRESH_TOKEN = REFRESH_TOKEN

        self._debug = True
        self._cache = True
        self.setDebugSave("vertexaiClaude")
        self.DataHeadler = SSEHandler

    async def chat2api(self, request, request_model_name: str = "", id: str = "") -> AsyncGenerator[
        str, None]:
        model = request.get('model', "")
        logger.name = f"vertexaiGeminiProvider.{id}.model.{model}"
        sendReady = openaiSendBodyHeandler()
        sendReady.header_openai(request)
        pushdata = sendReady.get_vertexai_gemini(
            PROJECT_ID=self.PROJECT_ID,
            CLIENT_ID=self.CLIENT_ID,
            CLIENT_SECRET=self.CLIENT_SECRET,
            REFRESH_TOKEN=self.REFRESH_TOKEN,
            MODEL=model
        )  # 改这里
        self.DataHeadler = SSEHandler(id, request_model_name)
        async for chunk in self.chat2api_super(request, request_model_name, id, pushdata):
            yield chunk



if __name__ == "__main__":
    async def main():
        from app.api_data import db
        providers, error = db.get_admin_provider( "v-gemini-1.5-pro")
        provider = providers[0]
        print(provider)
        interface = vertexaiGeminiProvider(provider['PROJECT_ID'], provider['CLIENT_ID'], provider['CLIENT_SECRET'], provider['REFRESH_TOKEN'],

                                   )
        interface.setDebugSave("vertexai_gemini_" + provider['mapped_model'])
        interface._debug = True
        interface._cache = True
        interface._db_cache = True
        model_name = provider['mapped_model']
        # djson = pyefun.读入文本("/Users/ll/Desktop/2024/ll-openai/app/provider/sendbody/vertexai_gemini_c2cc1845-277e-4ba2-86f7-1411491aa5fe_gemini-1.5-pro.txt")
        # djson = json.loads(djson)
        #
        # async for response in interface.chat2api(djson):
        #     print(response)

        async for response in interface.chat2api({
            "model": model_name,
            "messages": [{"role": "user", "content": "请用三句话描述春天。"}],
            "stream": True,
        }):
            print(response)

        print(interface.DataHeadler.get_stats())


    asyncio.run(main())
