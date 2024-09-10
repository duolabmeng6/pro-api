import asyncio
from typing import AsyncGenerator
from fastapi import HTTPException
from app.provider.baseProvider import baseProvider
from app.log import logger
from app.provider.openaiSSEHandler import openaiSSEHandler as SSEHandler  # 改这里
from app.provider.openaiSendBodyHeandler import openaiSendBodyHeandler


class openaiProvider(baseProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
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
        pushdata = sendReady.get_oepnai()  # 改这里

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
        model_test = [
            # "gpt-4o",
            # "glm-4-flash",
            # "doubao-pro-128k",
            # "moonshot-v1-128k",
            # "qwen2-72b",
            "deepseek-coder"
        ]
        for model_name in model_test:
            providers, error = db.get_user_provider("sk-111111", model_name)
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
