import json

import httpx
from openai import OpenAI

from app.aiEasy.aiEasy import aiEasy
from app.aiEasy.aiTool import aiTool

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

from duckduckgo_search import DDGS


@aiTool(
    query={
        "description": "搜索的关键词。",
    }
)
def search_duckduckgo(query: str) -> list:
    """使用DuckDuckGo搜索服务从互联网获取最新信息。无论用户输入什么内容，都进行搜索并返回结果。"""
    print("query", query)
    search_results = DDGS().text(keywords=query, region="wt-wt", safesearch="on", max_results=2)
    print("search_results", search_results)
    search_results = json.dumps(search_results)
    return search_results


aitool = aiEasy(client, model)
aitool.register_function(search_duckduckgo)

result = aitool.chat("搜索一下 laravel是什么", {
    "总结": "string",
    "参考链接": [
        {"标题": "string", "链接": "string"}
    ]
})
print("结果", result)
