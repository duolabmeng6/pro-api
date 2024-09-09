
from abc import ABC, abstractmethod


class chatInterface(ABC):
    @abstractmethod
    async def chat2api(self,request, request_model_name: str = "", id: str = "") -> any:
        """将openai的接口数据转换为对应provider的接口数据"""
        pass
