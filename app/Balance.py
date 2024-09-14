import random
from typing import List, Dict, Any, Optional

class Provider:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

class Balance:
    def __init__(self, name: str, providers_data: List[Dict[str, Any]]):
        self.name = name
        self.providers = {data['name']: Provider(data) for data in providers_data}
        self.weights = {name: provider.data.get('weight', 1) for name, provider in self.providers.items()}
        self.provider_names = list(self.providers.keys())
        self.current_index = -1
        self.current_weight = 0
        
        print(f"初始化的Balance名称: {self.name}")
        print("初始化的提供者:", list(self.providers.keys()))
        print("初始化的权重:", self.weights)

    def next(self) -> Optional[Provider]:
        while True:
            if self.current_weight == 0:
                for _ in range(len(self.provider_names)):
                    self.current_index = (self.current_index + 1) % len(self.provider_names)
                    current_name = self.provider_names[self.current_index]
                    self.current_weight = self.weights[current_name]
                    if self.current_weight > 0:
                        break
                else:
                    return None

            current_name = self.provider_names[self.current_index]
            provider = self.providers[current_name]
            self.current_weight -= 1
            return provider

if __name__ == "__main__":
    providers_data = [
        {
            "name": "Gemini1",
            "provider": "gemini",
            "mapped_model": "gemini-1.5-flash",
            "original_model": "gemini-1.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "api_key": "1",
            "weight": 1
        },
        {
            "name": "Gemini2",
            "provider": "gemini",
            "mapped_model": "gemini-1.5-flash",
            "original_model": "gemini-1.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "api_key": "2",
            "weight": 2
        },
        {
            "name": "Gemini3",
            "provider": "gemini",
            "mapped_model": "gemini-1.5-flash",
            "original_model": "gemini-1.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "api_key": "3",
            "weight": 0
        }
    ]
    balance = Balance("MyBalance", providers_data)
    balance2 = Balance("MyBalance2", providers_data)
    print("开始选择提供者:")
    for i in range(9):
        provider = balance.next()
        print(f"第 {i+1} 次选择: {provider.data['name']}")
        provider = balance2.next()
        print(f"第 {i+1} 次选择: {provider.data['name']}")
    print("选择结束")

