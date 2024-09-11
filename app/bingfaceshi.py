
import time
import threading
import aiohttp
import asyncio

url = "http://127.0.0.1:8000/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer sk-111111"
}
payload = {
    "model": "glm-4-flash",
    "temperature": 0.8,
    "top_p": 1,
    "frequency_penalty": 0,
    "presence_penalty": 0,
    "n": 1,
    "stream": False,
    "stream_options": {
        "include_usage": True
    },
    "messages": [
        {
            "role": "user",
            "content": "你是什么模型"
        }
    ]
}

# 添加计数器和锁
success_count = 0
failure_count = 0
count_lock = threading.Lock()

async def send_request(session, semaphore):
    async with semaphore:
        try:
            async with session.post(url, headers=headers, json=payload) as response:
                data = await response.text()
                print(data)
            return True
        except Exception as e:
            print(f"请求出错: {str(e)}")
            return False

async def run_test():
    semaphore = asyncio.Semaphore(1)  # 限制并发数为100
    async with aiohttp.ClientSession() as session:
        tasks = [send_request(session, semaphore) for _ in range(1)]
        results = await asyncio.gather(*tasks)

    success_count = sum(results)
    failure_count = len(results) - success_count
    print(f"成功请求数: {success_count}")
    print(f"失败请求数: {failure_count}")

if __name__ == "__main__":
    start_time = time.time()
    asyncio.run(run_test())
    end_time = time.time()
    print(f"测试完成，总耗时: {end_time - start_time:.2f} 秒")
