from app.provider.openai.openaiProvider import OpenAiInterface
from app.provider.models import RequestModel, Message


def test_openai_interface_chat():
    openai_interface = OpenAiInterface()
    request = RequestModel(
        stream=True,
        model="gpt-3.5-turbo",
        messages=[Message(role="user", content="你好，请问你是谁？")]
    )
    for response in openai_interface.chat(request):
        print(response)  # 打印每个 yield 的结果

    print("测试完成")


