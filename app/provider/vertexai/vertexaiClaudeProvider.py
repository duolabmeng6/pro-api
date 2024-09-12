import asyncio
from http.client import HTTPException
from typing import AsyncGenerator
from app.provider.baseProvider import baseProvider
from app.log import logger
from app.provider.vertexai.claudeSSEHandler import claudeSSEHandler as SSEHandler
from app.provider.openaiSendBodyHeandler import openaiSendBodyHeandler


class vertexaiClaudeProvider(baseProvider):
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
        logger.name = f"vertexaiClaudeProvider.{id}.model.{model}"
        sendReady = openaiSendBodyHeandler()
        sendReady.header_openai(request)
        pushdata = sendReady.get_vertexai_claude(
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
        providers, error = db.get_admin_provider( "claude-3-5-sonnet@20240620")
        provider = providers[0]
        print(provider)
        interface = vertexaiClaudeProvider(provider['PROJECT_ID'], provider['CLIENT_ID'], provider['CLIENT_SECRET'],
                                           provider['REFRESH_TOKEN'],
                                           )
        interface.setDebugSave("claude_" + provider['mapped_model'])
        interface._debug = False
        interface._cache = False
        interface._dbcache = False
        model_name = provider['mapped_model']
        # 读取JSON文件
        async for response in interface.chat2api({
            "model": model_name,
            "messages": [{"role": "user", "content": "描述冬天一句话"}],
            "stream": True,
        }):
            pass
            print(response)



    asyncio.run(main())
