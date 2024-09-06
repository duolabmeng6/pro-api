import random

import httpx
from openai import OpenAI

from app.aiEasy.aiTool import aiTool
from app.aiEasy.aiEasy import aiEasy

import os
from dotenv import load_dotenv
# 加载.env文件中的环境变量
load_dotenv(dotenv_path='../.env')
# 从环境变量中读取API密钥和基础URL
api_key = os.getenv('api_key')
base_url = os.getenv('base_url')
model = os.getenv('model', 'deepseek-coder')

# 确保必要的环境变量已设置
if not api_key or not base_url:
    raise ValueError("请在.env文件中设置OPENAI_API_KEY和OPENAI_BASE_URL")

api_key = 'sk-cba57e89745545a7b3192a54e2b04e77'
base_url = 'https://api.deepseek.com/v1'
model = "deepseek-coder"
client = OpenAI(
    api_key=api_key,  # API密钥
    base_url=base_url,  # 基础URL
    http_client=httpx.Client(
        # proxies="http://127.0.0.1:8888",
        # transport=httpx.HTTPTransport(local_address="0.0.0.0"),
        # verify=False
    )
)


@aiTool(
    location="城市和州，如加利福尼亚州旧金山 中国北京 中国上海",
    unit={
        "description": "使用的温度单位。根据用户所在位置推断。",
        "enum": ("华氏温度", "摄氏度")
    }
)
def get_weather(location: str, unit: str) -> str:
    """Get weather of an location, the user shoud supply a location first"""
    print("调用了函数", location, unit)
    随机值1 = random.randint(-10, 35)
    随机值2 = random.randint(-10, 35)
    return f"{随机值1} {随机值2} {unit}"


aitool = aiEasy(client, model)
aitool.register_function(get_weather)
result = aitool.chat("杭州天气如何？上海天气如何? 旧金山天气如何?", {
    "data:": [{
        "最低温度": "string",
        "最高温度": "string",
        "温度单位": "string 华氏度或者是摄氏度",
        "城市": "string",
        "舒适度": "string 一段描述温度的话",
    }]
})
print("结果:", result)
