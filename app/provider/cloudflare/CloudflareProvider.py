import asyncio
import json
import os
import time
from typing import AsyncGenerator
import httpx

from app.help import load_env
from app.provider.baseProvider import baseProvider
from app.log import logger


class CloudflareSendBodyHandler:
    def __init__(self, openai_body):
        if isinstance(openai_body, str):
            self.openai_body = json.loads(openai_body)
        else:
            self.openai_body = openai_body

    def get_chat_history(self):
        return self.openai_body.get('messages', [])


class CloudflareSSEHandler:
    def __init__(self, custom_id=None, model=""):
        self.custom_id = custom_id
        self.model = model
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.full_message_content = ""

    def generate_response(self):
        return {
            "id": f"chatcmpl-{self.custom_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": self.full_message_content
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

    def generate_sse_response(self, content=None):
        chunk = {
            "id": f"chatcmpl-{self.custom_id}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": None
                }
            ]
        }

        if content is None:
            chunk["choices"][0]["delta"] = {"role": "assistant"}
        elif content == "[DONE]":
            chunk["choices"][0]["finish_reason"] = "stop"
        else:
            chunk["choices"][0]["delta"] = {"content": content}

        return json.dumps(chunk)

    def handle_sse_data_line(self, line: str):
        return self.generate_sse_response(line)


class CloudflareProvider(baseProvider):
    def __init__(self, api_key: str, account_id: str):
        super().__init__()
        self.api_key = api_key
        self.account_id = account_id
        self.setDebugSave("cloudflare")

    async def chat2api(self, request, request_model_name: str = "", id: str = "") -> AsyncGenerator[str, None]:
        model = request.get('model', "")
        logger.name = f"cloudflareProvider.{id}.model.{model}"

        data_handler = CloudflareSSEHandler(id, request_model_name)

        url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/{model}"
        send_body = CloudflareSendBodyHandler(request)
        messages = send_body.get_chat_history()
        inputs = {"messages": messages}
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, headers=headers, json=inputs)
            result = response.json()
            data_handler.full_message_content = result['result']['response']

        if not request.get('stream'):
            yield data_handler.generate_response()
        else:
            for line in data_handler.full_message_content.splitlines():
                yield "data: " + data_handler.handle_sse_data_line(line)
            yield "data: " + data_handler.generate_sse_response("[DONE]")


if __name__ == "__main__":
    async def main():
        load_env()
        account_id = os.getenv('cloudflare_accounts')
        api_key = os.getenv('cloudflare_api_key')
        model_test = ["@cf/qwen/qwen1.5-14b-chat-awq"]

        for model_name in model_test:
            interface = CloudflareProvider(api_key, account_id)
            interface.setDebugSave(model_name)
            async for response in interface.chat2api({
                "model": model_name,
                "messages": [{"role": "user", "content": "请用三句话描述春天。"}],
                "stream": False,
            }):
                print(response)

    asyncio.run(main())
