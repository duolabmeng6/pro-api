import asyncio
import os

import httpx
from typing import Dict, Any, AsyncGenerator, Tuple
from fastapi import HTTPException
from app.provider.models import RequestModel, Message
import ujson as json
from app.help import generate_sse_response, build_openai_response
from app.log import logger
import jsonpath


class geminiProvider:
    def __init__(self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com/v1beta"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "*/*",
                "User-Agent": "curl/7.68.0",
            },
            timeout=httpx.Timeout(connect=15.0, read=600, write=30.0, pool=30.0),
            http2=False,  # 将 http2 设置为 False
            verify=True,
            follow_redirects=True,
        )
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

        self._debug = True
        self._cache = True
        self.setDebugSave("gemini")

    def setDebugSave(self, name="gemini"):
        name = name.replace("/", "-")
        # 获取当前脚本所在的目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构造文件的绝对路径
        self._debugfile_sse = os.path.join(current_dir + f"/debugdata/{name}_sse.txt")
        self._debugfile_data = os.path.join(current_dir + f"/debugdata/{name}_data.txt")

    async def _get_api_data(self, stream: bool, url: str, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        if stream:
            # Streamed request
            async with self.client.stream("POST", url, json=payload) as response:
                await self.raise_for_status(response)
                async for chunk in response.aiter_text():
                    chunk = chunk.strip()
                    if chunk:  # Ignore empty chunks
                        yield chunk
        else:
            # Non-streamed request
            response = await self.client.post(url, json=payload)
            await self.raise_for_status(response)
            response_text = response.content.decode("utf-8")
            yield response_text

    async def sendChatCompletions(self, request: RequestModel) -> AsyncGenerator[str, None]:
        logger.name = f"geminiProvider.{request.id}.request.model"
        payload = await self.get_payload(request)

        if request.stream:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:streamGenerateContent?alt=sse&key={self.api_key}"
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        logger.info(f"\r\n发送 {url} \r\n请求体:\r\n{json.dumps(payload, indent=2, ensure_ascii=False)}")

        # 调试部分修改
        debug_file = self._debugfile_sse if request.stream else self._debugfile_data
        if self._debug:
            error = False
            if self._cache:
                try:
                    if request.stream:
                        with open(debug_file, "r") as f:
                            for line in f:
                                line = line.strip()
                                if line != "":
                                    yield line
                                    error = True
                        return
                    else:
                        with open(debug_file, "r") as f:
                            data = f.read()
                            if data != "":
                                yield data
                                error = True

                except FileNotFoundError:
                    error = False
                    logger.warning(f"Debug file {debug_file} not found, it will be created in write mode.")
            if error:
                return

        file_handle = None
        if self._cache:
            mode = 'w' if request.stream else 'a'
            try:
                file_handle = open(debug_file, mode)
            except IOError as e:
                logger.error(f"Unable to open debug file {debug_file}: {e}")

        try:
            # 这里是真正的写的部分
            async for line in self._get_api_data(request.stream, url, payload):
                if self._cache and file_handle:
                    try:
                        file_handle.write(line + "\n")
                    except IOError as e:
                        logger.error(f"写入调试文件时出错: {e}")
                logger.info(f"收到数据\r\n{line}")
                yield line
        finally:
            # Ensure file closure
            if file_handle:
                try:
                    file_handle.close()
                except IOError as e:
                    logger.error(f"Error closing debug file: {e}")

    async def get_payload(self, request: RequestModel) -> Dict[str, Any]:
        contents = []
        for msg in request.messages:
            parts = []
            if isinstance(msg.content, list):
                for item in msg.content:
                    if item.type == "text":
                        parts.append({"text": item.text})
                    elif item.type == "image_url":
                        parts.append({
                            "inline_data": {
                                "mime_type": "image/jpeg",  # 假设是JPEG格式,可能需要根据实际情况调整
                                "data": item.image_url.url  # 这里可能需要将URL转换为base64编码的图像数据
                            }
                        })
            else:
                parts.append({"text": msg.content})

            role = "user"
            if msg.role == "system":
                role = "model"
            if msg.role == "assistant":
                role = "model"

            contents.append({"role": role, "parts": parts})

        topK = 40
        payload = {
            "contents": contents,
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
            "generationConfig": {
                "temperature": request.temperature if request.temperature is not None else 0.7,
                "maxOutputTokens": request.max_tokens if request.max_tokens is not None else 8192,
                "topP": request.top_p if request.top_p is not None else 0.95,
                "topK": topK
                # "topK": request.top_k if request.top_k is not None else 40
            }
        }

        # 添加其他可能的配置参数
        # if request.stop is not None:
        #     payload["generationConfig"]["stopSequences"] = request.stop

        return payload

    async def chat2api(self, request: RequestModel, request_model_name: str = "", id: str = "") -> AsyncGenerator[
        str, None]:

        try:
            genData = self.sendChatCompletions(request)
            first_chunk = await genData.__anext__()
        except Exception as e:
            raise HTTPException(status_code=404, detail=e)

        if not request.stream:
            content = await self.extract_content(first_chunk)
            await self.extract_usage(first_chunk)

            yield await build_openai_response(id, content, request_model_name, self.prompt_tokens,
                                              self.completion_tokens, self.total_tokens)

            return

        # 流处理的代码
        yield True
        yield await generate_sse_response(id, request_model_name)
        content = await self.extract_content_stream(first_chunk)
        yield await generate_sse_response(id, request_model_name, content=content)
        async for chunk in genData:
            content = await self.extract_content_stream(chunk)
            if isinstance(content, dict):
                if "error" in content:
                    logger.error(f"发生错误: {content['error']}")
                    continue
            yield await generate_sse_response(id, request_model_name, content=content)

        yield await generate_sse_response(id, request_model_name, content={"type": "end"})

    async def chat(self, request: RequestModel) -> AsyncGenerator[str, None]:
        try:
            async for chunk in self.sendChatCompletions(request):
                if request.stream:
                    content = await self.extract_content_stream(chunk)
                    if content['type'] == 'content':
                        yield content['content']
                    elif content['type'] == 'stop':
                        break
                else:
                    content = await self.extract_content(chunk)
                    yield content
                    break
        except Exception as e:
            logger.error(f"聊天过程中发生错误: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def raise_for_status(self, response: httpx.Response):
        if response.status_code == 200:
            return
        response_content = await response.aread()
        error_data = {
            "error": "上游服务器出现错误",
            "response_body": response_content.decode("utf-8"),
            "status_code": response.status_code
        }
        cjson = response_content.decode("utf-8")
        cjson = json.loads(cjson)
        logger.error(f"发生错误: {json.dumps(cjson, indent=4)}")
        raise HTTPException(status_code=500, detail=error_data)

    async def extract_content_stream(self, line: str) -> Dict[str, Any]:
        """
        解析SSE流数据行提取
        :param line: 数据行
        :return: 解析后的数据

        解析后的数据类型
        {"type": "content", "content": "你好"} # 内容
        {"type": "error", "content": ""} # 不返回就行
        {"type": "function_call", "function": {"name": "function_name", "arguments": "function_arguments"}} # 工具调用
        {"type": "stop", "content": "你好", "prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20} # 完成
        {"type": "end", "content": "[DONE]"} # 结束
        """
        try:
            if line.startswith("data: "):
                data = line[6:]
            elif line.startswith("data:"):
                data = line[5:]
            else:
                data = line

            data = json.loads(data)

            content = jsonpath.jsonpath(data, "$.candidates[0].content.parts[0].text")
            content = content[0] if content else ""

            usage = jsonpath.jsonpath(data, "$.usageMetadata")
            if usage:
                self.prompt_tokens = usage[0].get("promptTokenCount", 0)
                self.completion_tokens = usage[0].get("candidatesTokenCount", 0)
                self.total_tokens = usage[0].get("totalTokenCount", 0)

            return {
                "type": "content",
                "content": content,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens
            }
        except json.JSONDecodeError:
            logger.error(f"JSON解析错误,数据行: {line}")
            return {"type": "error", "content": "JSON解析错误"}
        except Exception as e:
            logger.error(f"提取流内容时发生错误: {str(e)}")
            return {"type": "error", "content": str(e)}

    async def extract_content(self, data: str) -> str:
        try:
            if isinstance(data, str):
                data = json.loads(data)
            # 使用jsonpath提取内容
            content = jsonpath.jsonpath(data, "$.candidates[0].content.parts[0].text")
            return content[0] if content else ""
        except json.JSONDecodeError:
            logger.error(f"JSON解析错误,数据行: {data}")
            return ""
        except Exception as e:
            logger.error(f"提取内容时发生错误: {str(e)}")
            return ""

    async def extract_usage(self, data: str) -> Tuple[int, int, int]:
        try:
            if isinstance(data, str):
                data = json.loads(data)
            usage = jsonpath.jsonpath(data, "$.usageMetadata")
            if usage:
                self.prompt_tokens = usage[0].get("promptTokenCount", 0)
                self.completion_tokens = usage[0].get("candidatesTokenCount", 0)
                self.total_tokens = usage[0].get("totalTokenCount", 0)
            return self.prompt_tokens, self.completion_tokens, self.total_tokens
        except Exception as e:
            logger.error(f"提取使用情况时发生错误: {str(e)}")
            return 0, 0, 0


if __name__ == "__main__":
    async def main():
        from app.database import Database
        db = Database("../api.yaml")
        providers, error = await db.get_user_provider("sk-111111", "gemini-1.5-flash")
        provider = providers[0]
        print(provider)
        gemini_interface = geminiProvider(provider['api_key'], provider['base_url'])
        gemini_interface.setDebugSave(provider['mapped_model'])
        gemini_interface._debug = True
        gemini_interface._cache = True
     
        # 读取JSON文件
        with open('./testdata/openai_fc.json', 'r', encoding='utf-8') as file:
            data = json.load(file)

        try:
            r = RequestModel.parse_obj(data)
        except ValueError as e:
            print(f"验证错误: {e}")

        # 使用创建的RequestModel对象
        async for response in gemini_interface.chat(r):
            logger.info("内容:" + response)


    asyncio.run(main())
