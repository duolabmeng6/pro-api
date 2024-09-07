import base64
from typing import AsyncGenerator

import httpx

import ujson as json
from duckduckgo_search.utils import json_dumps
from icecream import ic

from app.provider.httpxHelp import get_api_data2


class openaiSendBodyHeandler:
    def __init__(self, api_key, base_url, model):
        self.req = None
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def header_openai(self, send_body):
        # 检查send_body是str就转换为 json
        # 如果是对象直接使用
        if isinstance(send_body, str):
            request = json.loads(send_body)
        else:
            request = send_body
        self.req = request

    def get_oepnai(self):
        # 保持原有的OpenAI请求格式
        url = f"{self.base_url}/chat/completions"
        payload = self.req
        payload["model"] = self.model

        return {
            "url": url,
            "stream": payload.get("stream", False),
            "headers": {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "*/*",
                "User-Agent": "curl/7.68.0"
            },
            "body": payload
        }

    def get_Gemini(self):
        stream = self.req.get("stream", False)
        if stream:
            gemini_stream = "streamGenerateContent"
            url = f"{self.base_url}/models/{self.model}:{gemini_stream}?key={self.api_key}&alt=sse"
        else:
            gemini_stream = "generateContent"
            url = f"{self.base_url}/models/{self.model}:{gemini_stream}?key={self.api_key}"

        contents = []
        system_instruction = None

        for msg in self.req.get("messages", []):
            role = msg["role"]
            content = msg.get("content", "")

            if role == "system":
                system_instruction = content
                continue

            parts = []
            if isinstance(content, str):
                parts.append({"text": content})
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, str):
                        parts.append({"text": item})
                    elif isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append({"text": item["text"]})
                        elif item.get("type") == "image_url":
                            image_url = item["image_url"]["url"]
                            if image_url.startswith("data:image"):
                                _, encoded = image_url.split(",", 1)
                                image_data = base64.b64decode(encoded)
                                parts.append({
                                    "inline_data": {
                                        "mime_type": "image/jpeg",
                                        "data": base64.b64encode(image_data).decode()
                                    }
                                })
                            else:
                                parts.append({"image_url": image_url})

            contents.append({"role": "user" if role == "user" else "model", "parts": parts})

        # 处理工具
        tools = []
        if self.req.get("tools"):
            for tool in self.req["tools"]:
                if tool["type"] == "function":
                    function = tool["function"]
                    tools.append({
                        "function_declarations": [{
                            "name": function["name"],
                            "description": function["description"],
                            "parameters": function["parameters"]
                        }]
                    })

        # 构建 Gemini API 请求体
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.req.get("temperature", 0.7),
                "topP": self.req.get("top_p", 1),
                "topK": self.req.get("top_k", 40),
                "maxOutputTokens": self.req.get("max_tokens", 2048),
                "stopSequences": self.req.get("stop", []),
                "candidateCount": 1,
            },
        }

        # 只有在tools非空时才添加到payload
        if tools:
            payload["tools"] = tools

        # 正确处理 systemInstruction
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        # 添加安全设置
        safety_settings = []
        for category in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                         "HARM_CATEGORY_DANGEROUS_CONTENT"]:
            safety_settings.append({
                "category": category,
                "threshold": "BLOCK_NONE"
            })
        payload["safetySettings"] = safety_settings

        return {
            "url": url,
            "stream": stream,
            "headers": {
                "Content-Type": "application/json",
            },
            "body": payload
        }


import pyefun

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    # 加载.env文件中的环境变量
    load_dotenv(dotenv_path='../.env')
    # 从环境变量中读取API密钥和基础URL
    api_key = os.getenv('api_key')
    base_url = os.getenv('base_url')
    model = os.getenv('model', 'deepseek-coder')

    # httpx 日志
    import logging

    logging.getLogger("httpx").setLevel(logging.DEBUG)

    files = [
        "./sendbody/openai_search3b_glm-4-flash.txt"
        # "./sendbody/openai图片2.txt"

    ]
    with open(files[0], "r", encoding="utf-8") as f:
        body = f.read()
        # model = "glm-4v"
        # obj = openaiSendBodyHeandler(api_key="",
        #                              base_url="",
        #                              model=model)
        # obj.header_openai(body)
        # pushdata = obj.get_oepnai()

        model = "gemini-1.5-flash"
        obj = openaiSendBodyHeandler(api_key=api_key,
                                     base_url= base_url,
                                     model=model)
        obj.header_openai(body)
        print(json.dumps(obj.get_Gemini(), indent=4, ensure_ascii=False))
        pushdata = obj.get_Gemini()

        ic(pushdata)

        response = get_api_data2(pushdata)
        md5 = pyefun.取数据md5(response)
        pyefun.文件_写出(f"./savebody/{model}_{md5}_sse.txt", response)
