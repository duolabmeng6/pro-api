import asyncio
import json
import os
import time
from typing import AsyncGenerator

import cohere
import httpx

from app.help import load_env
from app.provider.baseProvider import baseProvider
from app.log import logger


class cohereSendBodyHeandler:
    def __init__(self, openai_body):
        if isinstance(openai_body, str):
            request = json.loads(openai_body)
        else:
            request = openai_body
        self.openai_body = request

    def get_chat_history(self):
        messages = self.openai_body.get('messages', [])
        chat_history = []
        for message in messages[:-1]:  # 排除最后一条消息，因为它将作为当前查询
            role = message['role']
            content = message['content']
            if role == 'user':
                chat_history.append({"role": "USER", "message": content})
            elif role == 'assistant':
                chat_history.append({"role": "CHATBOT", "message": content})
        return chat_history

    def get_message(self):
        messages = self.openai_body.get('messages', [])
        if messages:
            return messages[-1]['content']
        return ""


class cohereSSEHandler:
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

        # json_data = json.dumps(chunk, ensure_ascii=False)
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

        json_data = json.dumps(chunk, ensure_ascii=False)
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


class cohereProvider(baseProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.cohere.com/v1"):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url
        self.setDebugSave("cohere")
        self.DataHeadler = cohereSSEHandler

    async def chat2api(self, request, request_model_name: str = "", id: str = "") -> AsyncGenerator[
        str, None]:
        model = request.get('model', "command-r-plus-08-2024")
        logger.name = f"cohereProvider.{id}.model.{model}"
        co = cohere.AsyncClient(
            api_key=self.api_key,
            base_url=self.base_url,
            # httpx_client=httpx.Client(
            #     proxies="http://127.0.0.1:8888",
            #     transport=httpx.HTTPTransport(local_address="0.0.0.0"),
            #     verify=False
            # )
        )

        sendbody = cohereSendBodyHeandler(request)
        message = sendbody.get_message()
        chat_history = sendbody.get_chat_history()
        self.DataHeadler = cohereSSEHandler(id, model)
        if not request['stream']:
            chunk = co.chat(
                message=message,
                model=model,
                chat_history=chat_history,
                temperature=0.3,
                prompt_truncation="AUTO",
                citation_quality="accurate",
                # connectors=[{"id": "web-search"}]
            )
            self.DataHeadler.full_message_content = chunk.text
            self.DataHeadler.prompt_tokens = chunk.meta.tokens.input_tokens
            self.DataHeadler.completion_tokens = chunk.meta.tokens.output_tokens
            self.DataHeadler.total_tokens = chunk.meta.tokens.input_tokens + chunk.meta.tokens.output_tokens
            self.DataHeadler.tool_calls = None
            yield self.DataHeadler.generate_response()
            return

        response = co.chat_stream(
            message=message,
            model=model,
            chat_history=chat_history,
            temperature=0.3,
            prompt_truncation="AUTO",
            citation_quality="accurate",
#             connectors=[{"id": "web-search"}]
        )

        async for chunk in response:
            if chunk.event_type == "text-generation":
                yield "data: " + self.DataHeadler.handle_SSE_data_line(chunk.text)
            elif chunk.event_type == "stream-end":
                self.DataHeadler.full_message_content = chunk.response.text
                self.DataHeadler.prompt_tokens = chunk.response.meta.tokens.input_tokens
                self.DataHeadler.completion_tokens = chunk.response.meta.tokens.output_tokens
                self.DataHeadler.total_tokens = chunk.response.meta.tokens.input_tokens + chunk.response.meta.tokens.output_tokens
                self.DataHeadler.tool_calls = None
                yield "data: [DONE]"


if __name__ == "__main__":
    async def main():
        load_env()
        base_url = os.getenv('cohere_base_url')
        api_key = os.getenv('cohere_api_key')
        model_test = [
            "command-r-plus-08-2024"
        ]

        for model_name in model_test:
            interface = cohereProvider(api_key, base_url)
            interface.setDebugSave(f"{model_name}")
            content = ""
            async for response in interface.chat2api({
                "model": model_name,
                "messages": [{"role": "user", "content": "请用三句话描述春天。"}],
                "stream": True,
            }):
                print(response)


    asyncio.run(main())
