import asyncio
import uuid
import pyefun

from app.provider.httpxHelp import get_api_data

async def send_merlin_request(api_key, content, model):
    url = 'https://arcane.getmerlin.in/v1/thread/unified'
    headers = {
        'authority': 'arcane.getmerlin.in',
        'accept': 'text/event-stream, text/event-stream',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'authorization': 'Bearer ' + api_key,
        'content-type': 'application/json',
        'dnt': '1',
        'origin': 'https://www.getmerlin.in',
        'referer': 'https://www.getmerlin.in/',
        'sec-ch-ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Microsoft Edge";v="116"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1923.0',
        'x-merlin-version': 'web-merlin',
    }

    id = str(uuid.uuid4())
    chatId = str(uuid.uuid4())
    childId = str(uuid.uuid4())
    body = {"attachments": [], "chatId": chatId, "language": "AUTO",
            "message": {"childId": childId, "content": content, "context": "",
                        "id": id, "parentId": "root"},
            "metadata": {"merlinMagic": False, "webAccess": False}, "mode": "UNIFIED_CHAT", "model": model}

    senddata = {
        "url": url,
        "headers": headers,
        "body": body,
        "stream": True
    }
    async for chunk in get_api_data(senddata):
        yield chunk


if __name__ == "__main__":
    api_key = pyefun.读入文本("./api_key.txt")

    async def main():
        async for chunk in send_merlin_request(api_key, "你只需要回答我ok就可以了.", "gpt-4o-mini"):
            print(chunk)
            pyefun.文件_追加文本("./sse2.txt", chunk)

    asyncio.run(main())
