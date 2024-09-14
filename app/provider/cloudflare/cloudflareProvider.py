import asyncio
import json
import os
import time
from typing import AsyncGenerator
import httpx

from app.help import load_env
from app.provider.baseProvider import baseProvider
from app.log import logger


class cloudflareSendBodyHeandler:
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
        messages = self.openai_body.get('messages', [])
        if messages:
            return messages[-1]['content']
        return ""


class cloudflareSSEHandler:
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
        return self.generate_sse_response({'type': 'content', 'content': line})

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


class cloudflareProvider(baseProvider):
    def __init__(self, api_key: str, account_id: str):
        super().__init__()
        self.api_key = api_key
        self.setDebugSave("cloudflare")
        self.DataHeadler = cloudflareSSEHandler
        self.account_id = account_id

    async def chat2api(self, request, request_model_name: str = "", id: str = "") -> AsyncGenerator[
        str, None]:
        model = request.get('model', "")
        logger.name = f"cloudflareProvider.{id}.model.{model}"

        self.DataHeadler = cloudflareSSEHandler(id, request_model_name)

        url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/{model}"
        sendBody = cloudflareSendBodyHeandler(request)
        message = sendBody.get_chat_history()
        inputs = {
            "messages": message
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        with httpx.Client(timeout=120) as client:
            response = client.post(url, headers=headers, json=inputs)
            result = response.json()
            print(result)
            self.DataHeadler = cloudflareSSEHandler(id, model)
            self.DataHeadler.full_message_content = result['result']['response']
            self.DataHeadler.prompt_tokens = 0
            self.DataHeadler.completion_tokens = 0
            self.DataHeadler.total_tokens = 0
            self.DataHeadler.tool_calls = None
            if not request['stream']:
                yield self.DataHeadler.generate_response()
            else:
                yield "data: " + self.DataHeadler.handle_SSE_data_line(self.DataHeadler.full_message_content)
            yield "data: [DONE]"


if __name__ == "__main__":
    async def main():
        load_env()
        accounts = os.getenv('cloudflare_accounts')
        api_key = os.getenv('cloudflare_api_key')
        model_test = [
            "@cf/qwen/qwen1.5-14b-chat-awq"
        ]

        for model_name in model_test:
            interface = cloudflareProvider(api_key, accounts)
            interface.setDebugSave(f"{model_name}")
            content = ""
            async for response in interface.chat2api({
                "model": model_name,
                "messages": [{"role": "user", "content": "请用三句话描述春天。"}],
                # "stream": True,
                "stream": False,
            }):
                print(response)


    asyncio.run(main())
