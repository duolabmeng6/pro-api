import hashlib
import json

from fastapi import HTTPException
from typing import AsyncGenerator

import httpx

from app.db.logDB import CacheManager


async def raise_for_status(sendReady, response: httpx.Response):
    if response.status_code == 200:
        # print("raise_for_status",response.status_code )
        return
    response_content = await response.aread()
    error_data = {
        "error": "上游服务器出现错误",
        "response_body": response_content.decode("utf-8"),
        "status_code": response.status_code,
        "model": sendReady.get("model"),
        "body": sendReady.get("body"),
        "url": sendReady.get("url"),
    }
    raise HTTPException(status_code=500, detail=error_data)


client = httpx.AsyncClient(
    headers={
        "Content-Type": "application/json",
        "Accept": "*/*",
        "User-Agent": "curl/7.68.0",
    },
    timeout=httpx.Timeout(connect=15.0, read=600, write=30.0, pool=30.0),
    # http2=False,  # 将 http2 设置为 False
    verify=False,
    # follow_redirects=True,
    proxies={  # 使用字典形式来指定不同类型的代理
        # "http://": "http://127.0.0.1:8888",
        # "https://": "http://127.0.0.1:8888",  # 如果代理服务器支持 HTTP 和 HTTPS，则可以这样设置
    },
)


async def get_api_data(sendReady) -> AsyncGenerator[str, None]:
    DONE = False
    if sendReady["stream"]:
        async with client.stream("POST", sendReady["url"], headers=sendReady["headers"],
                                 json=sendReady["body"]) as response:
            await raise_for_status(sendReady, response)
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if line.startswith('data:'):  # 只处理 SSE 数据行
                        yield line
                        if line == "data: [DONE]":
                            DONE = True
            if not DONE:
                yield "data: [DONE]"
    else:
        # 非流式请求
        response = await client.post(sendReady["url"], headers=sendReady["headers"], json=sendReady["body"])
        await raise_for_status(sendReady, response)
        response_text = response.content.decode("utf-8")
        yield response_text


cacheManager = CacheManager()


async def get_api_data_cache(sendReady) -> AsyncGenerator[str, None]:
    cache_md5 = hashlib.md5(json.dumps(sendReady['body']).encode('utf-8')).hexdigest()
    cache = cacheManager.get_from_cache(cache_md5)
    if cache:
        print(f"命中缓存{cache_md5}次数: {cache.hit_count}")
        if sendReady["stream"]:
            data = cache.resp
            arr = data.split("\r\n")
            for line in arr:
                line = line.strip()
                if line != "":
                    yield line
        else:
            yield cache.resp
        return

    cacheData = ""
    DONE = False
    try:
        if sendReady["stream"]:
            async with client.stream("POST", sendReady["url"], headers=sendReady["headers"],
                                     json=sendReady["body"]) as response:
                await raise_for_status(sendReady, response)
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line.startswith('data:'):  # 只处理 SSE 数据行
                            cacheData += line + "\r\n"
                            if line == "data: [DONE]":
                                DONE = True
                            yield line

                if not DONE:
                    yield "data: [DONE]"

        else:
            # 非流式请求
            response = await client.post(sendReady["url"], headers=sendReady["headers"], json=sendReady["body"])
            await raise_for_status(sendReady, response)
            response_text = response.content.decode("utf-8")
            cacheData = response_text
            yield response_text

    finally:
        # 无论是流式还是非流式请求，都在这里保存缓存
        if cacheData:
            print(f"db Cache 保存{cache_md5}: {cacheData}")
            cacheManager.add_to_cache(cache_md5, json.dumps(sendReady["body"]), cacheData)




def get_api_data2(sendReady):
    import logging
    logging.getLogger("httpx").setLevel(logging.DEBUG)

    with httpx.Client(
            headers={
                "Content-Type": "application/json",
                "Accept": "*/*",
                "User-Agent": "curl/7.68.0",
            },
            timeout=httpx.Timeout(connect=15.0, read=600, write=30.0, pool=30.0),
            verify=False,
            proxies={
                # "http://": "http://127.0.0.1:8888",
                # "https://": "http://127.0.0.1:8888",
            }
    ) as client:
        if isinstance(sendReady["body"], str):
            response = client.post(sendReady["url"], headers=sendReady["headers"], data=sendReady["body"])
        else:
            response = client.post(sendReady["url"], headers=sendReady["headers"], json=sendReady["body"])

        print("===========")
        print(response.headers.items())
        print(response.status_code)
        print(response.text)
        response_text = response.content
        return response_text
