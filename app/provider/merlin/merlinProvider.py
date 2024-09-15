import asyncio
import json
import time
from typing import AsyncGenerator

from app.provider.baseProvider import baseProvider
from app.log import logger
from app.provider.merlin.merlin import send_merlin_request

class merlinSendBodyHeandler:
    def __init__(self, openai_body):
        if isinstance(openai_body, str):
            request = json.loads(openai_body)
        else:
            request = openai_body
        self.openai_body = request

    def get_chat_history(self):
        messages = self.openai_body.get('messages', [])
        return messages

    def get_message(self):
        # 把信息聚合成一条 比如 
        # system: 内容
        # user: 内容
        # assistant: 内容
        messages = self.get_chat_history()
        message = ""
        for item in messages:
            if item['role'] == 'system':
                message += f"system: {item['content']}\n"
            elif item['role'] == 'user':
                message += f"user: {item['content']}\n"
            elif item['role'] == 'assistant':
                message += f"assistant: {item['content']}\n"

        return message



class merlinSSEHandler:
    def __init__(self, custom_id=None, model=""):
        self.custom_id = custom_id
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.full_message_content = ""
        self.model = model
        self.tool_calls = []  # 新增: 用于存储完整的工具调用信息

    def generate_response(self):
        chunk = {
            "id": "chatcmpl-" + self.custom_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": self.full_message_content,
                        "tool_calls": self.tool_calls if self.tool_calls else None
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens
            }
        }

        # json_data = json.dumps(chunk)
        return chunk

    def generate_sse_response(self, content=None):
        current_timestamp = int(time.time())
        chunk = {
            "id": f"chatcmpl-{self.custom_id}",
            "object": "chat.completion.chunk",
            "created": current_timestamp,
            "model": self.model,
            "system_fingerprint": None,
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
        elif content['type'] == 'tool_calls':
            chunk["choices"][0]["delta"] = {"tool_calls": content['function']}
        elif content['type'] == 'stop':
            chunk["choices"][0]["delta"] = {}
            chunk["choices"][0]["finish_reason"] = "stop"
            chunk["usage"] = {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            }
        elif content['type'] == 'end':
            return "[DONE]"
        else:
            return None

        json_data = json.dumps(chunk)
        return f"{json_data}"

    def handle_SSE_data_line(self, line: str):
        # {"status":"success","data":{"content":"好的"}}
        # {"status":"system","data":{"content":" ","eventType":"DONE"}}
        if line.startswith("data:"):
            line = line[5:].strip()
        line = line.strip()
        if line == "[DONE]":
            return "[DONE]"
        if line == "":
            return None

        try:
            data = json.loads(line)
            content = data.get('data', {}).get('content', '')
            eventType = data.get('data', {}).get('eventType', '')
            if content != "":
                self.full_message_content += content
                return self.generate_sse_response({"type": "content", "content": content})
            if eventType == "DONE":
                return self.generate_sse_response({"type": "stop"})

            return None
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}\r\n{line}\r\n")
            return None
        except Exception as e:
            print(f"处理失败: {e}\r\n{line}\r\n")
            return None

    def get_stats(self):
        return {
            "full_message_content": self.full_message_content,
            "custom_id": self.custom_id,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "tool_calls": self.tool_calls
        }

    def handle_data_line(self, line: str):
        self.full_message_content = line
        response = self.generate_response()
        return response


class merlinProvider(baseProvider):
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.setDebugSave("merlin")
        self.DataHeadler = merlinSSEHandler

    async def chat2api(self, request, request_model_name: str = "", id: str = "") -> AsyncGenerator[
        str, None]:
        model = request.get("model","")
        stream = request.get('stream', False)
        logger.name = f"merlinProvider.{id}.model.{model}"

        sendbody = merlinSendBodyHeandler(request)
        message = sendbody.get_message()
        self.DataHeadler = merlinSSEHandler(id, request_model_name)
        logger.info(f"model:{ model}",)


        response = send_merlin_request(self.api_key, message, model)

        if not stream:
            async for chunk in response:
                self.DataHeadler.handle_SSE_data_line(chunk)
            yield self.DataHeadler.generate_response()
            return

        yield True
        async for chunk in response:
            out = self.DataHeadler.handle_SSE_data_line(chunk)
            if out:
                yield "data: " + out


if __name__ == "__main__":
    async def main():
        import pyefun
        api_key = pyefun.读入文本("api_key.txt")
        model_test = [
            "gpt-4o-mini",
            # "claude-3-haiku",
        ]

        for model_name in model_test:
            interface = merlinProvider(api_key)
            interface.setDebugSave(f"{model_name}")
            content = ""
            async for response in interface.chat2api({
                "model": model_name,
                "messages": [
                    # {"role": "system", "content": "你的名字叫小红。如果"},
                    {"role": "user", "content": "你是什么模型"},
                ],
                # "stream": True,
                "stream": True,
            }):
                print(response)


    asyncio.run(main())
