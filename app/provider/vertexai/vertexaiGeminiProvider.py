
import asyncio
from typing import AsyncGenerator
from http.client import HTTPException
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
        from api_data import db
        db = apiDB("../../api.yaml")
        providers, error = db.get_user_provider("sk-111111", "gemini-1.5-flash-001")
        provider = providers[0]
        print(provider)
        interface = vertexaiGeminiProvider(provider['PROJECT_ID'], provider['CLIENT_ID'], provider['CLIENT_SECRET'], provider['REFRESH_TOKEN'],

                                   )
        interface.setDebugSave("vertexai_gemini_" + provider['mapped_model'])
        interface._debug = False
        interface._cache = False
        interface._dbcache = False
        model_name = provider['mapped_model']
        # 读取JSON文件
        async for response in interface.chat2api({
            "model": model_name,
            "messages": [{"role": "user", "content": "请用三句话描述春天。"}],
            "stream": True,
        }):
            print(response)


    asyncio.run(main())
