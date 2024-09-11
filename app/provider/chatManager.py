from app.provider.chatInterface import chatInterface
import copy

class chatManager:
    def __init__(self, default_chat: str =""):
        self.chats = {}
        self.current_chat = default_chat

    def set_chat(self, chat_name: str, chat: chatInterface):
        self.chats[chat_name] = chat
        return self

    def chat(self, chat_name: str) -> chatInterface:
        if chat_name not in self.chats:
            return None
        return copy.deepcopy(self.chats[chat_name])

    def get_chat(self) -> chatInterface:
        if self.current_chat not in self.chats:
            raise ValueError("chat not set")
        return copy.deepcopy(self.chats[self.current_chat])


    
    async def chat2api(self, request, request_model_name: str = "", id: str = ""):
        return self.get_chat().chat2api(request, request_model_name, id)
    