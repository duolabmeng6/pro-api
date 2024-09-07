import ujson as json
import os
import jsonpath


# 用于接收openaisdk发送的参数然后得到其他大模型的发送参数
class openaiSendBodyHeandler:
    def __init__(self, api_key, base_url, model):
        self.payload = None
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def header_openai(self, send_body):
        request = json.loads(send_body)
        self.payload = request

    def get_oepnai(self):
        url = f"{self.base_url}/chat/completions"
        payload = self.payload
        payload["model"] = self.model

        return {
            "url": url,
            "headers": {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "*/*",
                "User-Agent": "curl/7.68.0"
            },
            "body": payload
        }

    def get_Gemini(self):
        gemini_stream = "streamGenerateContent"
        url = f"{self.base_url}/models/{self.model}:{gemini_stream}?key={self.api_key}"

        payload = {}
        payload["model"] = self.model

        return {
            "url": url,
            "headers": {
                "Content-Type": "application/json",
            },
            "body": payload
        }

# 测试代码
if __name__ == "__main__":
    files = [
        "./sendbody/openai_search3a_glm-4-flash.txt"
    ]
    with open(files[0], "r", encoding="utf-8") as f:
        body = f.read()
        obj = openaiSendBodyHeandler(api_key="api_key", base_url="https://open.bigmodel.cn/api/paas/v4", model="glm-4")
        obj.header_openai(body)
        # print(json.dumps(obj.get_oepnai(), indent=4, ensure_ascii=False))

        obj.model = "gemini-1.5-flash"
        print(json.dumps(obj.get_Gemini(), indent=4, ensure_ascii=False))
