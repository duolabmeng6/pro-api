import asyncio
import os
import time
import uuid
import httpx
from typing import Dict, Any, AsyncGenerator, Tuple
from fastapi import HTTPException
from app.provider.models import RequestModel, Message
import ujson as json
from app.log import logger
import jsonpath


async def build_openai_response(id: str, response_data: dict, model: str, prompt_tokens: int, completion_tokens: int,
                                total_tokens=int):
    current_timestamp = int(time.time())
    response = {
        "id": id,
        "object": "chat.completion",
        "created": current_timestamp,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                },
                "logprobs": None,
                "finish_reason": None
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
        "system_fingerprint": ""
    }

    if response_data['type'] == 'content':
        response["choices"][0]["message"]["content"] = response_data['content']
        response["choices"][0]["finish_reason"] = "stop"
    elif response_data['type'] == 'function_call':
        response["choices"][0]["message"]["tool_calls"] = response_data['function']
        response["choices"][0]["finish_reason"] = "tool_calls"
    if response_data['type'] == 'stop':
        response["choices"][0]["message"]["content"] = response_data['content']
        response["choices"][0]["finish_reason"] = "stop"

    return response


async def generate_sse_response(id, model, content=None):
    current_timestamp = int(time.time())
    chunk = {
        "id": f"chatcmpl-{id}",
        "object": "chat.completion.chunk",
        "created": current_timestamp,
        "model": model,
        "system_fingerprint": "",
        "choices": [
            {
                "index": 0,
                "delta": {},
                "logprobs": None,
                "finish_reason": None
            }
        ]
    }

    if content is None:
        chunk["choices"][0]["delta"] = {"role": "assistant", "content": ""}
    elif content['type'] == 'content':
        chunk["choices"][0]["delta"] = {"content": content['content']}
    elif content['type'] == 'stop':
        chunk["choices"][0]["delta"] = {}
        chunk["choices"][0]["finish_reason"] = "stop"
        chunk["usage"] = {
            "prompt_tokens": content.get('prompt_tokens', 0),
            "completion_tokens": content.get('completion_tokens', 0),
            "total_tokens": content.get('total_tokens', 0)
        }
    elif content['type'] == 'end':
        return "data: [DONE]"
    else:
        return None

    json_data = json.dumps(chunk, ensure_ascii=False)
    return f"data: {json_data}\n\n"


class geminiProvider:
    def __init__(self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com/v1beta"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
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
        model = request.model
        gemini_stream = "streamGenerateContent" if request.stream else "generateContent"
        if self.base_url.endswith("v1beta"):
            url = "https://generativelanguage.googleapis.com/v1beta/models/{model}:{stream}?key={api_key}".format(
                model=model, stream=gemini_stream, api_key=self.api_key)
        elif self.base_url.endswith("v1"):
            url = "https://generativelanguage.googleapis.com/v1/models/{model}:{stream}?key={api_key}".format(
                model=model, stream=gemini_stream, api_key=self.api_key)
        else:
            url = f"{self.base_url}/models/{model}:{gemini_stream}?key={self.api_key}"

        if request.stream:
            url += "&alt=sse"

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
        messages = []
        systemInstruction = None
        function_arguments = None
        for msg in request.messages:
            if msg.role == "assistant":
                msg.role = "model"
            tool_calls = None
            if isinstance(msg.content, list):
                content = []
                for item in msg.content:
                    if item.type == "text":
                        text_message = {"text": item.text}
                        content.append(text_message)
                    elif item.type == "image_url":
                        image_message = {"inline_data": {"mime_type": "image/jpeg", "data": item.image_url.url}}
                        content.append(image_message)
            else:
                content = [{"text": msg.content}]
                tool_calls = msg.tool_calls

            if tool_calls:
                tool_call = tool_calls[0]
                function_arguments = {
                    "functionCall": {
                        "name": tool_call.function.name,
                        "args": json.loads(tool_call.function.arguments)
                    }
                }
                messages.append(
                    {
                        "role": "model",
                        "parts": [function_arguments]
                    }
                )
            elif msg.role == "tool":
                function_call_name = function_arguments["functionCall"]["name"]
                messages.append(
                    {
                        "role": "function",
                        "parts": [{
                            "functionResponse": {
                                "name": function_call_name,
                                "response": {
                                    "name": function_call_name,
                                    "content": {
                                        "result": msg.content,
                                    }
                                }
                            }
                        }]
                    }
                )
            elif msg.role != "system":
                messages.append({"role": msg.role, "parts": content})
            elif msg.role == "system":
                systemInstruction = {"parts": content}

        payload = {
            "contents": messages,
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
                "topK": 40  # Gemini API 可能不支持自定义 top_k
            }
        }
        if systemInstruction:
            payload["system_instruction"] = systemInstruction

        for field, value in request.model_dump(exclude_unset=True).items():
            if field == "tools":
                payload.update({
                    "tools": [{
                        "function_declarations": [tool["function"] for tool in value]
                    }],
                    "tool_config": {
                        "function_calling_config": {
                            "mode": "AUTO"
                        }
                    }
                })

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
            # await self.extract_usage(first_chunk)
            content = await build_openai_response(id, content, request_model_name, self.prompt_tokens,
                                                  self.completion_tokens,
                                                  self.total_tokens)

            yield content
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

        解析后的数据类型用于生成openai_response
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

    async def extract_content(self, data: str) -> Dict[str, Any]:
        try:
            if isinstance(data, str):
                json_data = json.loads(data)
            else:
                json_data = data

            # 提取函数调用信息
            function_calls = jsonpath.jsonpath(json_data, "$.candidates[0].content.parts[*].functionCall")

            # 提取使用情况
            usage = json_data.get("usageMetadata", {})

            # 提取完成原因
            finish_reason = json_data.get("candidates", [{}])[0].get("finishReason", "")

            if function_calls:

                tool_calls = []
                for func_call in function_calls:
                    tool_calls.append({
                        "id": uuid.uuid4().hex,
                        "type": "function",
                        "function": {
                            "name": func_call["name"],
                            "arguments": json.dumps(func_call["args"]),
                        }
                    })

                return {"type": "function_call", "function": tool_calls}
            elif finish_reason == "STOP":
                # 完成
                content = jsonpath.jsonpath(json_data, "$.candidates[0].content.parts[0].text")
                content = content[0] if content else ""
                return {
                    "type": "stop",
                    "content": content,
                    "prompt_tokens": usage.get("promptTokenCount", 0),
                    "completion_tokens": usage.get("candidatesTokenCount", 0),
                    "total_tokens": usage.get("totalTokenCount", 0)
                }
            else:
                # 普通内容
                content = jsonpath.jsonpath(json_data, "$.candidates[0].content.parts[0].text")
                content = content[0] if content else ""
                return {
                    "type": "content",
                    "content": content
                }

        except json.JSONDecodeError:
            logger.error(f"JSON解析错误,数据行: {data}")
            return {"type": "error", "content": "JSON 解析错误"}
        except Exception as e:
            logger.error(f"提取内容时发生错误: {str(e)}")
            return {"type": "error", "content": "数据解析错误"}

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
        gemini_interface.setDebugSave("weather-geminia_" + provider['mapped_model'])
        gemini_interface._debug = True
        gemini_interface._cache = True

        # 读取JSON文件
        with open('./testdata/openai_fc_2.json', 'r', encoding='utf-8') as file:
            data = json.load(file)

        try:
            r = RequestModel.parse_obj(data)
        except ValueError as e:
            print(f"验证错误: {e}")

        payload = await gemini_interface.get_payload(r)
        print(json.dumps(payload, indent=2, ensure_ascii=False))

        # async for response in gemini_interface.chat2api(r):
        #     # logger.info(response)
        #     print(json.dumps(response, indent=2, ensure_ascii=False))


    asyncio.run(main())
