import httpx
from numpy.distutils.conv_template import header
from openai import OpenAI
import os
from dotenv import load_dotenv
# 加载.env文件中的环境变量
load_dotenv(dotenv_path='../.env')
# 从环境变量中读取API密钥和基础URL
api_key = os.getenv('api_key')
base_url = os.getenv('base_url')
model = os.getenv('model', 'deepseek-chat')

# 确保必要的环境变量已设置
if not api_key or not base_url:
    raise ValueError("请在.env文件中设置OPENAI_API_KEY和OPENAI_BASE_URL")

client = OpenAI(
    api_key=api_key,  # API密钥
    base_url=base_url,  # 基础URL
    http_client=httpx.Client(
        # proxies="http://127.0.0.1:8888",
        # transport=httpx.HTTPTransport(local_address="0.0.0.0"),
        # verify=False
    )
)

# 定义一个Java示例程序
java_demo = """
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("你好，世界！");
    }
}
"""

# 使用OpenAI API提交Java示例程序并流式返回结果
stream = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": "你是一个Java编程专家。"},
        {"role": "user", "content": f"请评论以下Java代码并提供改进建议：\n\n{java_demo}"}
    ],
    temperature=0.7,
    max_tokens=150,
    stream=True,
    extra_headers = {
        "id": f"a"
    }
)

# 打印API流式响应
print("OpenAI API 流式响应:")
for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # 最后打印一个换行
