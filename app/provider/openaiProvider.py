import asyncio
import os
import httpx
from typing import Dict, Any, AsyncGenerator, Tuple
from fastapi import HTTPException

from app.provider.httpxHelp import get_api_data
from app.provider.models import Message
import ujson as json
from app.log import logger
from app.provider.openaiSSEHandler import openaiSSEHandler
from app.provider.openaiSendBodyHeandler import openaiSendBodyHeandler
import pyefun


class openaiProvider:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.DataHeadler = openaiSSEHandler
        self._debug = True
        self._cache = True
        self.setDebugSave("openai")

    def setDebugSave(self, name="openai"):
        name = name.replace("/", "-")
        # 获取当前脚本所在的目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构造文件的绝对路径
        self._debugfile_sse = os.path.join(current_dir + f"/debugdata/{name}_sse.txt")
        self._debugfile_data = os.path.join(current_dir + f"/debugdata/{name}_data.txt")
        self.debug_file = ""

    async def debugRtCache(self, request):
        self.debug_file = self._debugfile_sse if request.get("stream", False) else self._debugfile_data
        if self._debug:
            error = False
            if self._cache:
                logger.info(f"使用缓存{self.debug_file}")
                try:
                    data = pyefun.读入文本(self.debug_file)
                    if not request.get("stream", False):
                        if data != "":
                            yield data

                    arr = pyefun.分割文本(data, "\n")
                    for line in arr:
                        line = line.strip()
                        if line != "":
                            yield line
                            error = True

                except FileNotFoundError:
                    error = False
                    logger.warning(f"Debug file {self.debug_file} not found, it will be created in write mode.")
            if error:
                yield "停止"
                return
            if pyefun.文件是否存在(self.debug_file):
                pyefun.删除文件(self.debug_file)

    async def sendChatCompletions(self, request) -> AsyncGenerator[str, None]:
        id = request.get('id', "")
        model = request.get('model', "")
        logger.name = f"openaiProvider.{id}.request.model"
        sendReady = openaiSendBodyHeandler(self.api_key, self.base_url, model)
        sendReady.header_openai(request)
        pushdata = sendReady.get_oepnai()
        url = pushdata["url"]
        body = pushdata["body"]

        logger.info(f"\r\nsend {url} \r\nbody:\r\n{json.dumps(body, indent=4, ensure_ascii=False)}")

        # 调试部分 不要看
        async for i in self.debugRtCache(request):
            if i == "停止":
                return
            else:
                yield i

        async for line in get_api_data(pushdata):
            if self._cache:
                if request.get("stream", False):
                    pyefun.文件_追加文本(self.debug_file, line)
                else:
                    pyefun.文件_写出(self.debug_file, line)

            logger.info(f"收到数据\r\n{line}")
            yield line

    async def chat2api(self, request, request_model_name: str = "", id: str = "") -> AsyncGenerator[
        str, None]:

        try:
            genData = self.sendChatCompletions(request)
            first_chunk = await genData.__anext__()
        except Exception as e:
            logger.error("报错了chat2api %s", e)
            raise HTTPException(status_code=404, detail=e)

        self.DataHeadler = openaiSSEHandler(id, request_model_name)
        if not request.get("stream", False):
            content = self.DataHeadler.handle_data_line(first_chunk)
            yield content
            stats_data = self.DataHeadler.get_stats()
            logger.info(f"SSE 数据流迭代完成，统计信息：{stats_data}")
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
        stats_data = self.DataHeadler.get_stats()
        logger.info(f"SSE 数据流迭代完成，统计信息：{stats_data}")
        # logger.info(f"转换为普通：{handler.generate_response()}")


if __name__ == "__main__":
    async def main():
        from app.database import Database
        db = Database("../api.yaml")
        model_test = [
            "gpt-4o",
            # "glm-4-flash",
            # "doubao-pro-128k",
            # "moonshot-v1-128k",
            # "qwen2-72b",
            # "deepseek-coder"
        ]
        for model_name in model_test:
            providers, error = await db.get_user_provider("sk-111111", model_name)
            provider = providers[0]
            api_key = provider['api_key']
            base_url = provider['base_url']
            model_name = provider['mapped_model']
            # print(provider)
            print("正在测试", model_name)
            interface = openaiProvider(api_key, base_url)
            interface.setDebugSave(f"{model_name}_{provider['provider']}")
            interface._debug = True
            interface._cache = True

            content = ""
            async for response in interface.chat2api({
                "model": model_name,
                "messages": [{"role": "user", "content": "请用三句话描述春天。"}],
                "stream": False,
            }):
                # content += response
                # logger.info( response)
                logger.info(response)


    asyncio.run(main())
