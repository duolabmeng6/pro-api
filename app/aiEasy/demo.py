import json
import base64

import httpx
from openai import OpenAI

import os
from dotenv import load_dotenv
from openai.types.chat import ChatCompletionSystemMessageParam

# 加载.env文件中的环境变量
load_dotenv(dotenv_path='../.env')
# 从环境变量中读取API密钥和基础URL
api_key = os.getenv('api_key')
base_url = os.getenv('base_url')
model = os.getenv('model', 'deepseek-coder')

# 确保必要的环境变量已设置
if not api_key or not base_url:
    raise ValueError("请在.env文件中设置OPENAI_API_KEY和OPENAI_BASE_URL")

client = OpenAI(
    api_key=api_key,  # API密钥
    base_url=base_url,  # 基础URL
    http_client=httpx.Client(
        proxies="http://127.0.0.1:8888",
        transport=httpx.HTTPTransport(local_address="0.0.0.0"),
        verify=False
    )
)


# 调用函数 上传图片问是什么东西

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# 图片路径
image_path = "../img.png"

# 获取base64编码的图片
base64_image = encode_image(image_path)

# 创建包含图片的消息
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "这张图片里有什么?"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]
    }
]

# 调用API
response = client.chat.completions.create(
    model="glm-4v",  # 使用支持图像识别的模型
    messages=messages,
)
print(response)
exit()


# Define the search functions (mock implementations for Baidu, Google, and Bing)
def search_baidu(keyword):
    """Search for the keyword on Baidu"""
    return f"{keyword}是一个技术博主"


def search_google(keyword):
    """Search for the keyword on Google"""
    return f"{keyword}是一个后端工程师"


def search_bing(keyword):
    """Search for the keyword on Bing"""
    return f"{keyword}是一个Python爱好者"


# Define the tools in JSON format for OpenAI function calling
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_baidu",
            "description": "从百度搜索引擎中搜索关键词",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词"
                    }
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_google",
            "description": "从Google搜索引擎中搜索关键词",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词"
                    }
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_bing",
            "description": "从Bing搜索引擎中搜索关键词",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词"
                    }
                },
                "required": ["keyword"]
            }
        }
    }
]

# Mapping functions to their names
available_functions = {
    "search_baidu": search_baidu,
    "search_google": search_google,
    "search_bing": search_bing
}


def search(keyword):
    messages = [{"role": "user", "content": f"Search 汇总百度、谷歌、必应三个搜索引擎关于'{keyword}'的结果"}]

    print(f"初始消息: {messages}")  # 调试信息

    # 第一次请求：决定使用哪些工具
    response = client.chat.completions.create(model=model, messages=messages, tools=tools, tool_choice="auto",
                                              stream=True)

    response_message = None
    for chunk in response:
        if chunk.choices[0].delta.tool_calls:
            if response_message is None:
                response_message = chunk.choices[0].delta
            else:
                for i, call in enumerate(chunk.choices[0].delta.tool_calls):
                    if i >= len(response_message.tool_calls):
                        response_message.tool_calls.append(call)
                    else:
                        if call.function.arguments:
                            response_message.tool_calls[i].function.arguments += call.function.arguments

    if response_message is None or not response_message.tool_calls:
        print("未收到有效的工具调用响应")
        return "未能获取搜索结果"

    tool_calls = response_message.tool_calls

    print(f"AI决定使用的工具: {[call.function.name for call in tool_calls]}")  # 调试信息

    messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        try:
            # 移除重复的 JSON 对象
            clean_args = tool_call.function.arguments.split('}')[0] + '}'
            function_args = json.loads(clean_args)
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            print(f"原始参数字符串: '{tool_call.function.arguments}'")
            continue

        if 'keyword' not in function_args:
            print(f"缺少 'keyword' 参数: {function_args}")
            continue

        function_response = available_functions[function_name](**function_args)

        print(f"调用函数 {function_name} 的结果: {function_response}")  # 调试信息

        messages.append({
            "tool_call_id": tool_call.id,
            "role": "tool",
            "name": function_name,
            "content": function_response
        })

    # 第二次请求：汇总结果（流式）
    try:
        second_response = client.chat.completions.create(model=model, messages=messages, stream=True)
        full_response = ""
        for chunk in second_response:
            if chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content
                print(chunk.choices[0].delta.content, end="", flush=True)  # 实时打印输出
        print()  # 打印换行
        return full_response
    except Exception as e:
        print(f"发生错误: {e}")
        print(f"消息内容: {messages}")
        return "处理结果时发生错误"


# 示例使用
result = search("xindoo")
print(f"最终结果: {result}")
