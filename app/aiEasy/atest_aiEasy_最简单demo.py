import httpx
from openai import OpenAI

from app.aiEasy.aiEasy import aiEasy

import os
from dotenv import load_dotenv
# 加载.env文件中的环境变量
load_dotenv(dotenv_path='../.env')
# 从环境变量中读取API密钥和基础URL
api_key = os.getenv('api_key')
base_url = os.getenv('base_url')
model = os.getenv('model', 'deepseek-coder')


client = OpenAI(
    api_key=api_key,  # API密钥
    base_url=base_url,  # 基础URL
    http_client=httpx.Client(
        # proxies="http://127.0.0.1:8888",
        # transport=httpx.HTTPTransport(local_address="0.0.0.0"),
        # verify=False
    )
)


def search_baidu(keyword):
    """从百度搜索引擎中搜索关键词"""
    print("搜索百度")
    return f"{keyword}是一个技术博主"


def search_google(keyword):
    """从Google搜索引擎中搜索关键词"""
    print("搜索谷歌")
    return f"{keyword}是一个后端工程师"


def search_bing(keyword):
    """从Bing搜索引擎中搜索关键词"""
    print("搜索必应")
    return f"{keyword}是一个Python爱好者"


aitool = aiEasy(client, model)
aitool.register_function(search_baidu)
aitool.register_function(search_google)
aitool.register_function(search_bing)

result = aitool.chat("汇总百度、谷歌、必应三个搜索引擎关于xindoo的结果")
print("结果", result)
