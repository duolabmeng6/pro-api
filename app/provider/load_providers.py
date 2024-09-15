import asyncio
import json
from app.log import logger
from app.provider.chatManager import chatManager
from app.provider.openai.openaiProvider import openaiProvider
from app.provider.gemini.geminiProvider import geminiProvider
from app.provider.vertexai.vertexaiClaudeProvider import vertexaiClaudeProvider
from app.provider.vertexai.vertexaiGeminiProvider import vertexaiGeminiProvider


def load_providers(db):
    ai_manager = chatManager()

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
        elif provider == "cohere":
            from app.provider.cohere.cohereProvider import cohereProvider
            chat = cohereProvider(providerConfig.get("api_key", ""), providerConfig.get("base_url", ""))
        elif provider == "cloudflare":
            from app.provider.cloudflare.CloudflareProvider import CloudflareProvider
            chat = CloudflareProvider(providerConfig.get("api_key", ""), providerConfig.get("account_id", ""))
        elif provider == "merlin":
            from app.provider.merlin.merlinProvider import merlinProvider
            api_key = providerConfig.get("api_key", "")
            chat = merlinProvider(api_key)


        if not chat:
            logger.info(f"未知的提供商类型: {provider}")
            continue
        # 生成唯一的名称
        logger.info(f"添加提供商: {name}")
        # 将聊天实例添加到 ai_manager
        ai_manager.set_chat(name, chat)
        save_chat[name] = True
    logger.info(f"token: {db.tokens}")

    return ai_manager


if __name__ == "__main__":
    async def init():
        from app.api_data import db
        ai_manager = load_providers(db)
        request = """
    {
        "model": "@cf/qwen/qwen1.5-14b-chat-awq",
        "messages": [
            {
                "role": "user",
                "content": "请用三句话描述春天。"
            }
        ],
        "stream": true
    }
        
        """
        # request = json.loads(request)
        # data = ai_manager.chat("openai_智谱清言").chat2api(request, "glm-4-flash", "test")
        # async for response in data:
        #    logger.info(response)
        #
        request = json.loads(request)

        data = ai_manager.chat("cloudflare_cloudflare").chat2api(request, "@cf/qwen/qwen1.5-14b-chat-awq", "test")
        async for response in data:
           logger.info(response)
    asyncio.run(init())