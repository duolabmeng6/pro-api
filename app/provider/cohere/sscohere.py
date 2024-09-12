import cohere
import httpx

from app.aiEasy.agen import base_url

co = cohere.Client("",
                   httpx_client=httpx.Client(
                       proxies="http://127.0.0.1:8888",
                       transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                       verify=False
                   ),
                   base_url = "https://api.cohere.com/v1",
                   )


# response = co.chat(
#     chat_history=[
#         {"role": "USER", "message": "谁发现了万有引力？"},
#         {
#             "role": "CHATBOT",
#             "message": "被公认为发现万有引力的人是艾萨克-牛顿爵士",
#         },
#     ],
#     message="他是哪一年出生的？",
# model="command-r-plus-08-2024"
# )
#
# print(response)


response = co.chat_stream(
    chat_history=[
        {"role": "USER", "message": "谁发现了万有引力？"},
        {
            "role": "CHATBOT",
            "message": "被公认为发现万有引力的人是艾萨克-牛顿爵士",
        },
    ],
    message="他是哪一年出生的？",
model="command-r-plus-08-2024"
)
for chunk in response:
    if chunk.event_type == 'stream-start':
        print(f"开始流式传输: generation_id={chunk.generation_id}, is_finished={chunk.is_finished}")
    elif chunk.event_type == 'text-generation':
        print(f"生成文本: {chunk.text}", end='', flush=True)
    elif chunk.event_type == 'stream-end':
        print(f"\n流式传输结束: finish_reason={chunk.finish_reason}, is_finished={chunk.is_finished}")
        print(f"输入tokens: {chunk.response.meta.tokens.input_tokens}")
        print(f"输出tokens: {chunk.response.meta.tokens.output_tokens}")
        print(f"生成的文本: {chunk.response.text}")
        print(f"聊天历史: {chunk.response.chat_history}")
        print(f"响应ID: {chunk.response.response_id}")
    else:
        print(f"未知事件类型: {chunk.event_type}")
