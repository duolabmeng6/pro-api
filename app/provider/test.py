import asyncio
import json
import os

from app.apiDB import apiDB
from app.provider.chatManager import chatManager
from app.provider.openai.openaiProvider import openaiProvider
from app.provider.gemini.geminiProvider import geminiProvider
from app.provider.vertexai.vertexaiClaudeProvider import vertexaiClaudeProvider
from app.provider.vertexai.vertexaiGeminiProvider import vertexaiGeminiProvider


def load_providers(db):
    ai_manager = chatManager()
    # db = apiDB(os.path.join(os.path.dirname(__file__), '../api.yaml'))

    # 获取所有提供商配置
    all = db.get_all_provider()

    save_chat = {}
    # 遍历每个提供商配置
    for providerConfig in all:
        provider = providerConfig.get("provider", "")
        chat = None
        name = f"{providerConfig.get('provider', '')}_{providerConfig.get('name', '')}"
        if save_chat.get(name):
            continue

        if provider == "openai":
            chat = openaiProvider(providerConfig.get("api_key", ""), providerConfig.get("base_url", ""))
        elif provider == "gemini":
            chat = geminiProvider(providerConfig.get("api_key", ""), providerConfig.get("base_url", ""))
        elif provider == "vertexai_gemini":
            chat = vertexaiGeminiProvider(
                providerConfig.get("PROJECT_ID", ""),
                providerConfig.get("CLIENT_ID", ""),
                providerConfig.get("CLIENT_SECRET", ""),
                providerConfig.get("REFRESH_TOKEN", "")
            )
        elif provider == "vertexai_claude":
            chat = vertexaiClaudeProvider(
                providerConfig.get("PROJECT_ID", ""),
                providerConfig.get("CLIENT_ID", ""),
                providerConfig.get("CLIENT_SECRET", ""),
                providerConfig.get("REFRESH_TOKEN", "")
            )

        if not chat:
            print(f"未知的提供商类型: {provider}")
            continue
        # 生成唯一的名称
        print(f"添加提供商: {name}")
        # 将聊天实例添加到 ai_manager
        ai_manager.set_chat(name, chat)
        save_chat[name] = True
    return ai_manager


if __name__ == "__main__":
    async def init():
        db = apiDB(os.path.join(os.path.dirname(__file__), '../api.yaml'))
        ai_manager = load_providers(db)
        request = """
    {
        "model": "glm-4-flash",
        "messages": [
            {
                "role": "user",
                "content": "请用三句话描述春天。"
            }
        ],
        "stream": true
    }
        
        """
        request = json.loads(request)
        data = ai_manager.chat("openai_智谱清言").chat2api(request, "glm-4-flash", "test")
        async for response in data:
           print(response)

    asyncio.run(init())