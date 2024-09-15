import base64
import os
import time
import httpx
import ujson as json
from fastapi import HTTPException

from app.provider.httpxHelp import get_api_data2
import pyefun
import app.help as help

from collections import deque

class CircularList:
    """循环列表类，用于管理循环队列。"""
    
    def __init__(self, items):
        """初始化循环列表。"""
        self.queue = deque(items)

    def next(self):
        """返回下一个元素，并将其移动到队列末尾。"""
        if not self.queue:
            return None
        item = self.queue.popleft()
        self.queue.append(item)
        return item

    def to_dict(self):
        """返回队列的字典表示。"""
        return {
            'queue': list(self.queue)
        }
        
# 定义不同位置的循环列表
claude_35s_location = CircularList(["us-east5", "europe-west1"])
claude_3s_location = CircularList(["us-east5", "us-central1", "asia-southeast1"])
claude_3o_location = CircularList(["us-east5"])
claude_3h = CircularList(["us-east5", "us-central1", "europe-west1", "europe-west4"])
gemini_location = CircularList(["us-central1", "us-east4", "us-west1", "us-west4", "europe-west1", "europe-west2"])




token_cache = {}

def get_access_token(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN):
    TOKEN_URL = 'https://www.googleapis.com/oauth2/v4/token'
    now = time.time()

    if CLIENT_ID not in token_cache:
        token_cache[CLIENT_ID] = {"access_token": "", "expiry": 0}

    if token_cache[CLIENT_ID]["access_token"] and now < token_cache[CLIENT_ID]["expiry"] - 120:
        return token_cache[CLIENT_ID]["access_token"]
    try:
        with httpx.Client() as client:
            response = client.post(TOKEN_URL, json={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": REFRESH_TOKEN,
                "grant_type": "refresh_token"
            })
        data = response.json()
        token_cache[CLIENT_ID]["access_token"] = data["access_token"]
        token_cache[CLIENT_ID]["expiry"] = now + data["expires_in"]
        access_token = token_cache[CLIENT_ID]["access_token"]
    except httpx.RequestError as e:
        error_data = {
            "error": "网络请求错误",
            "detail": str(e),
            "response_body": TOKEN_URL,
        }
        raise HTTPException(status_code=503, detail=error_data)
    except Exception as e:
        error_data = {
            "error": "vertexai access_token 获取失败",
            "detail": str(e),
            "response_body": TOKEN_URL,
        }
        raise HTTPException(status_code=429, detail=error_data)

    return access_token


class openaiSendBodyHeandler:
    def __init__(self, api_key="", base_url="", model=""):
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
        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "User-Agent": "curl/7.68.0"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return {
            "url": url,
            "stream": payload.get("stream", False),
            "headers": headers,
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
            if isinstance(content, str) and content != '':
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

            if parts == []:
                continue
            if role == "user":
                contents.append({"role": "user", "parts": parts})
            else:
                contents.append({"role": "model", "parts": parts})

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
        # payload["safetySettings"] = safety_settings

        return {
            "url": url,
            "stream": stream,
            "headers": {
                "Content-Type": "application/json",
            },
            "body": payload
        }

    def get_vertexai_gemini(self, PROJECT_ID,
                            CLIENT_ID,
                            CLIENT_SECRET,
                            REFRESH_TOKEN,
                            MODEL
                            ):

        ready = self.get_Gemini()

        access_token = get_access_token(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)
        location = gemini_location.next()

        API_ENDPOINT = f"{location}-aiplatform.googleapis.com"
        if ready["stream"]:
            api_url = f"https://{API_ENDPOINT}/v1/projects/{PROJECT_ID}/locations/{location}/publishers/google/models/{MODEL}:streamGenerateContent?alt=sse"
        else:
            api_url = f"https://{API_ENDPOINT}/v1/projects/{PROJECT_ID}/locations/{location}/publishers/google/models/{MODEL}:generateContent"

        return {
            "url": api_url,
            "stream": ready["stream"],
            "headers": {
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {access_token}",

            },
            "body": ready['body']
        }

    def get_vertexai_claude(self,
                            PROJECT_ID,
                            CLIENT_ID,
                            CLIENT_SECRET,
                            REFRESH_TOKEN,
                            MODEL
                            ):

        stream = self.req.get("stream", False)

        # 构建 Claude API 请求体
        payload = {
            "anthropic_version": "vertex-2023-10-16",
            # "model": self.model,
            "max_tokens": self.req.get("max_tokens", 1024),
            "messages": [],
            "stream": stream
        }
        system_content = None
        # 处理消息
        for msg in self.req.get("messages", []):
            role = msg["role"]
            content = msg.get("content", "")
            if role == "system":
                system_content = content
                continue
            if role == "user":
                role = "user"
            else:
                role = "assistant"

            claude_msg = {"role": role, "content": []}

            if isinstance(content, str):
                claude_msg["content"].append({"type": "text", "text": content})
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, str):
                        claude_msg["content"].append({"type": "text", "text": item})
                    elif isinstance(item, dict):
                        if item.get("type") == "text":
                            claude_msg["content"].append({"type": "text", "text": item["text"]})
                        elif item.get("type") == "image_url":
                            image_url = item["image_url"]["url"]
                            if image_url.startswith("data:image"):
                                _, encoded = image_url.split(",", 1)
                                claude_msg["content"].append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": encoded
                                    }
                                })
                            else:
                                claude_msg["content"].append({
                                    "type": "image",
                                    "source": {
                                        "type": "url",
                                        "url": image_url
                                    }
                                })
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                continue
            if role == "tool":
                claude_msg = {
                    "role": "user",
                    "content": msg.get("content", "")
                }

            payload["messages"].append(claude_msg)

        if system_content:
            payload["system"] = system_content
        # 处理工具
        if self.req.get("tools"):
            payload["tools"] = []
            for tool in self.req["tools"]:
                if tool["type"] == "function":
                    function = tool["function"]
                    claude_tool = {
                        "name": function["name"],
                        "description": function["description"],
                        "input_schema": {
                            "type": "object",
                            "properties": function["parameters"].get("properties", {}),
                            "required": function["parameters"].get("required", [])
                        }
                    }
                    payload["tools"].append(claude_tool)

        if "claude-3-5-sonnet" in MODEL:
            location = claude_35s_location
        elif "claude-3-opus" in MODEL:
            location = claude_3o_location   
        elif "claude-3-sonnet" in MODEL:
            location = claude_3s_location
        elif "claude-3-haiku" in MODEL:
            location = claude_3h

        location = location.next()
        
        url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{location}/publishers/anthropic/models/{MODEL}:streamRawPredict"
        access_token = get_access_token(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)
        return {
            "url": url,
            "stream": stream,
            "headers": {
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {access_token}",

            },
            "body": payload
        }


if __name__ == "__main__":
    help.load_env()

    # 从环境变量中读取API密钥和基础URL
    api_key = os.getenv('api_key')
    base_url = os.getenv('base_url')
    model = os.getenv('model', 'deepseek-coder')

    files = [
        # "./sendbody/openai_search3b_glm-4-flash.txt"
        "./自留测试数据/openai_普通问题.txt"
        # "./sendbody/openai图片2.txt"
        # "/Users/ll/Desktop/2024/ll-openai/app/provider/sendbody/vertexai_gemini_weather-gemini-1.5-flash-001a_gemini-1.5-flash-001.txt"

    ]
    with open(files[0], "r", encoding="utf-8") as f:
        body = f.read()
        # model = "glm-4v"
        # obj = openaiSendBodyHeandler(api_key="",
        #                              base_url="",
        #                              model=model)
        # obj.header_openai(body)
        # pushdata = obj.get_oepnai()

        # model = "gemini-1.5-flash"
        # obj = openaiSendBodyHeandler(api_key=api_key,
        #                              base_url= base_url,
        #                              model=model)
        # obj.header_openai(body)
        # print(json.dumps(obj.get_Gemini(), indent=4, ensure_ascii=False))
        # pushdata = obj.get_Gemini()
        # ic(pushdata)
        # response = get_api_data2(pushdata)
        # md5 = pyefun.取数据md5(response)
        # pyefun.文件_写出(f"./savebody/{model}_{md5}_sse.txt", response)
        #
        model = "gemini-1.5-flash"
        obj = openaiSendBodyHeandler(api_key=os.getenv('api_key'),
                                     base_url=os.getenv('base_url'),
                                     model=os.getenv('model', 'gemini-1.5-flash'))
        obj.header_openai(body)
        pushdata = obj.get_vertexai_gemini(
            PROJECT_ID=os.getenv('PROJECT_ID'),
            CLIENT_ID=os.getenv('CLIENT_ID'),
            CLIENT_SECRET=os.getenv('CLIENT_SECRET'),
            REFRESH_TOKEN=os.getenv('REFRESH_TOKEN'),
            MODEL=model,
        )

        # model = "claude-3-5-sonnet@20240620"
        # obj = openaiSendBodyHeandler(api_key=os.getenv('api_key'),
        #                              base_url=os.getenv('base_url'),
        #                              model=os.getenv('model', 'claude-3-5-sonnet@20240620'))
        # obj.header_openai(body)
        # pushdata = obj.get_vertexai_claude(
        #     PROJECT_ID=os.getenv('PROJECT_ID'),
        #     CLIENT_ID=os.getenv('CLIENT_ID'),
        #     CLIENT_SECRET=os.getenv('CLIENT_SECRET'),
        #     REFRESH_TOKEN=os.getenv('REFRESH_TOKEN'),
        #     MODEL=model,
        # )

        print(pushdata)
        response = get_api_data2(pushdata)
        md5 = pyefun.取数据md5(response)
        if pushdata['stream']:
            pyefun.文件_写出(f"./savebody/{model}_{md5}_sse.txt", response)
        else:
            pyefun.文件_写出(f"./savebody/{model}_{md5}_data.json", response)
