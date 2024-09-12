import os

from typing import AsyncGenerator
import pyefun
from fastapi import HTTPException

from app.log import logger
from app.provider.httpxHelp import get_api_data, get_api_data_cache


class baseProvider:
    def __init__(self):
        self._debug = False
        self._cache = False
        self._db_cache = False
        self.setDebugSave("openai")
        self.DataHeadler = None

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
                    logger.info(f"缓存不存在{self.debug_file}")

            if error:
                yield "停止"
                return
            if pyefun.文件是否存在(self.debug_file):
                pyefun.删除文件(self.debug_file)

    async def sendChatCompletions(self, pushdata) -> AsyncGenerator[str, None]:
        # logger.info(f"\r\nsend {url} \r\nbody:\r\n{json.dumps(body, indent=4, ensure_ascii=False)}")
        # 调试部分 不要看
        async for i in self.debugRtCache(pushdata):
            if i == "停止":
                return
            else:
                yield i

        # 看这里 ==========
        if self._db_cache:
            datas = get_api_data_cache(pushdata)
        else:
            datas = get_api_data(pushdata)

        async for line in datas:
            if self._cache:
                if pushdata.get("stream", False):
                    pyefun.文件_追加文本(self.debug_file, line)
                    logger.info(f"{self.debug_file}追加数据\r\n{line}")
                else:
                    pyefun.文件_写出(self.debug_file, line)
                    logger.info(f"{self.debug_file}写入数据\r\n{line}")

            if self._debug:
                logger.info(f"收到数据\r\n{line}")
            yield line

    async def chat2api_super(self, request, request_model_name: str = "", id: str = "", pushdata="") -> AsyncGenerator[
        str, None]:
        pass


        try:
            genData = self.sendChatCompletions(pushdata)
            first_chunk = await genData.__anext__()
        except Exception as e:
            logger.error("报错了chat2api %s", e)
            raise HTTPException(status_code=404, detail=e)

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

        DONE = False
        async for chunk in genData:
            content = self.DataHeadler.handle_SSE_data_line(chunk)
            if content == "[DONE]":
                DONE = True
                continue
            if content:
                yield "data: " + content
        if not DONE:
            yield "data: [DONE]"
