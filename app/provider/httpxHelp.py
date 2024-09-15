import hashlib
import json
import re
from typing import AsyncGenerator
from fastapi import HTTPException
import httpx
from app.log import logger
from app.api_data import db

if db.config_server.get("admin_server", False):
    from app.db.logDB import CacheManager
    cacheManager = CacheManager()

client = httpx.AsyncClient(
    headers={
        "Content-Type": "application/json",
        "Accept": "*/*",
        "User-Agent": "curl/7.68.0",
    },
    timeout=httpx.Timeout(connect=120.0, read=600, write=120.0, pool=120.0),
    verify=False,
    proxies={
        # "http://": "http://127.0.0.1:8888",
        # "https://": "http://127.0.0.1:8888",
    },
)

async def raise_for_status(sendReady, response: httpx.Response):
    if response.status_code == 200:
        return
    response_content = await response.aread()
    newurl = sendReady.get("url")
    domain_pattern = r'https?://([^/]+)/?'
    match = re.search(domain_pattern, newurl)
    if match:
        domain = match.group(1)
    else:
        domain = newurl
    error_data = {
        "error": "上游服务器出现错误",
        "response_body": response_content.decode("utf-8"),
        "status_code": response.status_code,
        "domain": domain,
    }
    raise HTTPException(status_code=500, detail=error_data)

async def get_api_data(sendReady) -> AsyncGenerator[str, None]:
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
                        if line.startswith('data:'):
                            yield line
        else:
            response = await client.post(sendReady["url"], headers=sendReady["headers"], json=sendReady["body"])
            await raise_for_status(sendReady, response)
            response_text = response.content.decode("utf-8")
            yield response_text
    except httpx.RequestError as e:
        logger.error(f"网络请求错误: {e} {sendReady}")
        # e.request.url.host
        raise HTTPException(status_code=503, detail={"error": "网络请求错误", "detail": str(e)})
    except Exception as e:
        logger.error(f"未知错误: {e} {sendReady}")
        raise HTTPException(status_code=500, detail={"error": "上游服务器出现未知错误", "detail": str(e)})

async def get_api_data_cache(sendReady) -> AsyncGenerator[str, None]:
    cache_md5 = hashlib.md5(json.dumps(sendReady['body']).encode('utf-8')).hexdigest()
    cache = cacheManager.get_from_cache(cache_md5)
    if cache:
        logger.info(f"命中缓存 {cache_md5} 次数: {cache.hit_count}")
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

    logger.info(f"没有命中缓存 {cache_md5}")
    cacheData = ""
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
                        if line.startswith('data:'):
                            cacheData += line + "\r\n"
                            yield line
        else:
            response = await client.post(sendReady["url"], headers=sendReady["headers"], json=sendReady["body"])
            await raise_for_status(sendReady, response)
            response_text = response.content.decode("utf-8")
            cacheData = response_text
            yield response_text
    except httpx.RequestError as e:
        logger.error(f"网络请求错误: {e} {sendReady}")
        raise HTTPException(status_code=503, detail={"error": "网络请求错误", "detail": str(e)})
    except Exception as e:
        logger.error(f"未知错误: {e} {sendReady}")
        raise HTTPException(status_code=500, detail={"error": "上游服务器出现未知错误", "detail": str(e)})
    finally:
        if cacheData:
            logger.info(f"缓存保存 {cache_md5}")
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
            timeout=httpx.Timeout(connect=120, read=600, write=120, pool=120),
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