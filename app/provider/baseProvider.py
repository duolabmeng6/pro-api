import os
from typing import Dict, Any, AsyncGenerator, Tuple
from app.provider.httpxHelp import get_api_data, get_api_data_cache
from app.log import logger
import pyefun


class baseProvider:
    def __init__(self):
        self._debug = True
        self._cache = True
        self._dbcache = True
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

    async def sendChatCompletions(self, pushdata) -> AsyncGenerator[str, None]:
        # logger.info(f"\r\nsend {url} \r\nbody:\r\n{json.dumps(body, indent=4, ensure_ascii=False)}")
        # 调试部分 不要看
        async for i in self.debugRtCache(pushdata):
            if i == "停止":
                return
            else:
                yield i

        # 看这里 ==========
        if self._dbcache:
            datas = get_api_data_cache(pushdata)
        else:
            datas = get_api_data(pushdata)

        async for line in datas:
            if self._cache:
                if pushdata.get("stream", False):
                    pyefun.文件_追加文本(self.debug_file, line)
                    logger.info(f"{debug_file}追加数据\r\n{line}")
                else:
                    pyefun.文件_写出(self.debug_file, line)
                    logger.info(f"{debug_file}写入数据\r\n{line}")

            if self._debug:
                logger.info(f"收到数据\r\n{line}")
            yield line

    async def chat2api(self, request, request_model_name: str = "", id: str = "") -> AsyncGenerator[
        str, None]:
        pass

        # model = request.get('model', "")
        # logger.name = f"openaiProvider.{id}.request.model"
        #
        # sendReady = openaiSendBodyHeandler(self.api_key, self.base_url, model)
        # sendReady.header_openai(request)
        # pushdata = sendReady.get_oepnai()
        #
        # try:
        #     genData = self.sendChatCompletions(pushdata)
        #     first_chunk = await genData.__anext__()
        # except Exception as e:
        #     logger.error("报错了chat2api %s", e)
        #     raise HTTPException(status_code=404, detail=e)
        #
        # self.DataHeadler = SSEHandler(id, request_model_name)
        # if not request.get("stream", False):
        #     content = self.DataHeadler.handle_data_line(first_chunk)
        #     yield content
        #     return
        #
        # # 流处理的代码
        # yield True
        # yield "data: " + self.DataHeadler.generate_sse_response(None)
        # content = self.DataHeadler.handle_SSE_data_line(first_chunk)
        # if content:
        #     yield "data: " + content
        # async for chunk in genData:
        #     content = self.DataHeadler.handle_SSE_data_line(chunk)
        #     if content == "[DONE]":
        #         yield "data: [DONE]"
        #         break
        #     if content:
        #         yield "data: " + content
        #
