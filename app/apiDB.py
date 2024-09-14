import asyncio
import json
import yaml
from typing import List, Dict, Tuple
from fastapi.logger import logger
from patsy.user_util import balanced
from app.Balance import Balance


class apiDB:
    def __init__(self, content: str):
        # 初始化数据结构
        self.tokens: List[str] = []  # 存储API密钥
        self.tokensKV: Dict[str, Dict] = {}  # 存储每个API密钥对应的详细信息
        self.providers: List[Dict] = []  # 存储所有提供者的信息
        self.providersKV: Dict[str, List[Dict]] = {}  # 按原始模型名称存储提供者信息
        self.server_default: str = ""  # 服务器默认模型
        self.config_server: Dict = {}  # 服务器配置

        try:
            conf = yaml.safe_load(content)
            if conf:
                self.update_config(conf)
            else:
                logger.error("配置文件 'api.yaml' 为空。请检查文件内容。")
        except FileNotFoundError:
            logger.error(f"配置文件 'api.yaml' 未找到。请确保文件存在于正确的位置。")
        except yaml.YAMLError:
            logger.error("配置文件 'api.yaml' 格式不正确。请检查 YAML 格式。")

    def update_config(self, config_data: Dict):
        """更新配置信息"""
        providers = []
        for index, provider in enumerate(config_data['providers']):
            model_dict = {}
            for model in provider['model']:
                if isinstance(model, str):
                    model_dict[model] = model
                elif isinstance(model, dict):
                    model_dict.update({new: old for old, new in model.items()})
            provider['model'] = model_dict
            config_data['providers'][index] = provider

            for original_model, mapped_model in model_dict.items():
                weight = 1
                balance = provider.get('balance')  # [{'gemini-1.5-pro': 1}, {'gemini-1.5-flash': 1}]
                if balance:
                    # 循环balance检查key得到权重
                    for item in balance:
                        if original_model in item:
                            weight = item[original_model]
                            break

                item = {
                    "name": provider.get('name'),
                    "provider": provider.get('provider'),
                    "mapped_model": mapped_model,  # 转换的模型名称 转发的话提交这个模型名称
                    "original_model": original_model,  # 请求的模型名称
                    "base_url": provider.get('base_url'),
                    "api_key": provider.get('api_key'),
                    "weight": weight,
                }
                # 加入所有其他的属性到这里item
                # 将provider中的其他属性添加到item中
                for key, value in provider.items():
                    if key not in ["name", "provider", "model", "base_url", "api_key", "balance"]:
                        item[key] = value
                providers.append(item)

        self.providers = providers
        self.providersKV = {}

        # 构建providersKV字典
        for provider in providers:
            if provider['original_model'] in self.providersKV:
                self.providersKV[provider['original_model']].append(provider)
            else:
                self.providersKV[provider['original_model']] = [provider]

        # 更新tokens和tokens_data
        self.tokens = [item["api_key"] for item in config_data['tokens']]
        self.tokensKV = {token["api_key"]: token for token in config_data['tokens']}

        self.config_server = config_data['server']
        self.server_default = self.config_server.get("default_model", False)

        # logger.info(json.dumps(config_data, indent=4, ensure_ascii=False))

    def verify_token(self, api_key: str) -> bool:
        """验证API密钥是否有效"""
        if 'all' in self.tokens:
            api_key = 'all'

        return api_key in self.tokens

    def get_all_provider(self):
        return self.providers

    def get_admin_provider(self, model_name: str) -> Tuple[List[Dict], str]:
        """获取用户可用的提供者列表"""
        usability_model = self.providersKV.get(model_name, [])
        if not usability_model:
            if not self.server_default:
                return [], f"模型:{model_name}没有可用渠道"
            usability_model = self.providersKV.get(self.server_default, [])
            if not usability_model:
                return [], f"模型:{model_name}没有可用渠道,也没有设置兜底模型 server.default_model"
            return usability_model, ""
        return usability_model, ""

    def get_user_provider(self, api_key: str, model_name: str) -> Tuple[List[Dict], str]:
        """获取用户可用的提供者列表"""
        if 'all' in self.tokens:
            api_key = 'all'

        if api_key not in self.tokens:
            return [], "没有授权"

        user_use_model = set(self.tokensKV[api_key].get('model', []))

        if "all" not in user_use_model and not any(is_model_allowed(um, model_name) for um in user_use_model):
            return [], f"用户无权使用模型: {model_name}"

        usability_model = self.providersKV.get(model_name, [])
        if not usability_model:
            if not self.server_default:
                return [], f"模型:{model_name}没有可用渠道"
            usability_model = self.providersKV.get(self.server_default, [])
            if not usability_model:
                return [], f"模型:{model_name}没有可用渠道,也没有设置兜底模型 server.default_model"
            return usability_model, ""

        if "all" in user_use_model:
            return usability_model, ""

        filtered_usability_model = []
        for model in usability_model:
            for user_model in user_use_model:
                if user_model == model['original_model']:
                    filtered_usability_model.append(model)
                    break

        return filtered_usability_model, "成功"

    def get_all_models(self, api_key):
        # 返回openai的models格式
        if api_key not in self.tokens:
            return []

        user_models = self.tokensKV[api_key].get('model', [])
        all_models = []

        if "all" in user_models:
            all_models = list(self.providersKV.keys())
        else:
            for model in user_models:
                if model.endswith('*'):
                    all_models.extend([m for m in self.providersKV.keys() if m.startswith(model[:-1])])
                elif model in self.providersKV:
                    all_models.append(model)

        return [
            {
                "id": model,
                "object": "model",
                "owned_by": "pro-api",
            }
            for model in set(all_models)
        ]


def is_model_allowed(user_model: str, model_name: str) -> bool:
    if user_model == "all":
        return True
    if user_model.endswith('*'):
        return model_name.startswith(user_model[:-1])
    return user_model == model_name


if __name__ == "__main__":
    import pyefun


    def init():
        config = pyefun.读入文本("./api.yaml")
        db = apiDB(config)
        # ret = db.verify_token("sk-abcdefg")
        # print("token状态", ret)
        # ret = db.verify_token("sk-111111")
        # print("token状态", ret)
        api_key = "sk-111111"
        model = "qwen2-72b"
        model2 = "gemini-1.5-pro"

        provider, err = db.get_user_provider(api_key, model)
        print("配置:", err, json.dumps(provider, indent=4))

        provider2, err = db.get_user_provider(api_key, model2)
        print("配置:", err, json.dumps(provider, indent=4))
        balance = Balance(api_key + model, provider2)
        balance = Balance(api_key + model2, provider)


        for i in range(10):
            p = balance.next()
            print(p.data)

        for i in range(10):
            p = balance.next()
            print(p.data)

        yield


    asyncio.run(init())
