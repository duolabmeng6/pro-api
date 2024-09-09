import asyncio
import json
import httpx
from app.apiDB import Database


def test_gemini():
    async def gemini():
        db = Database("../api.yaml")
        providers, error = db.get_user_provider("sk-111111", "gemini-1.5-flash")
        provider = providers[0]
        api_key = provider['api_key']
        base_url = provider['base_url']

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:streamGenerateContent?alt=sse&key={api_key}"

        headers = {
            'Content-Type': 'application/json'
        }

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": "你会什么"}
                    ]
                }
            ]
        }

        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code == 200:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]  # Remove the "data: " prefix
                            try:
                                # Parse the JSON response from the stream
                                parsed_data = json.loads(data)
                                print(json.dumps(parsed_data, indent=2, ensure_ascii=False))
                            except json.JSONDecodeError:
                                print(f"数据解析错误: {data}")
                else:
                    # For non-200 responses, read the entire response before logging it
                    error_content = await response.aread()
                    print(f"请求失败，状态码: {response.status_code}")
                    print(f"响应内容: {error_content.decode('utf-8')}")

    asyncio.run(gemini())
