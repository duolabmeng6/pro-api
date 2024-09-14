import asyncio
from typing import AsyncGenerator
from app.provider.baseProvider import baseProvider
from app.log import logger
from app.provider.openaiSSEHandler import openaiSSEHandler as SSEHandler  # 改这里
from app.provider.openaiSendBodyHeandler import openaiSendBodyHeandler

class openaiProvider(baseProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url
        # 检查base_url 最后是/就删除
        self.base_url = self.base_url.rstrip("/")
        self.setDebugSave("openai")
        self.DataHeadler = SSEHandler

    async def chat2api(self, request, request_model_name: str = "", id: str = "") -> AsyncGenerator[
        str, None]:
        model = request.get('model', "")
        logger.name = f"openaiProvider.{id}.model.{model}"
        sendReady = openaiSendBodyHeandler(self.api_key, self.base_url, model)
        sendReady.header_openai(request)
        pushdata = sendReady.get_oepnai()  # 改这里
        self.DataHeadler = SSEHandler(id, request_model_name)
        async for chunk in self.chat2api_super(request, request_model_name, id, pushdata):
            yield chunk


if __name__ == "__main__":
    async def main():
        model_name = "gpt-4o"
        interface = openaiProvider("", base_url)
        async for response in interface.chat2api({
            "model": model_name,
            "messages": [{"role": "user", "content": "请用三句话描述春天。"}],
            "stream": True,
        }):
            print(response)



        return
        from app.api_data import db
        model_test = [
            # "gpt-4o",
            # "glm-4-flash",
            # "doubao-pro-128k",
            # "moonshot-v1-128k",
            # "qwen2-72b",
            "deepseek-chat"
        ]
        for model_name in model_test:
            providers, error = db.get_user_provider("sk-ll666666", model_name)
            provider = providers[0]
            api_key = provider['api_key']
            base_url = provider['base_url']
            model_name = provider['mapped_model']
            # print(provider)
            print("正在测试", model_name)
            interface = openaiProvider(api_key, base_url)
            interface.setDebugSave(f"{model_name}_{provider['provider']}")
            interface._debug = True
            interface._cache = False
            # interface._dbcache = True

            content = ""
            async for response in interface.chat2api({
                "model": model_name,
                "messages": [{"role": "user", "content": "请用三句话描述春天。"}],
                "stream": True,
            }):
                # content += response
                # logger.info( response)
                print(response)


    asyncio.run(main())
