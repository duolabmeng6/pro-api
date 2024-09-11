import apiDB
import pyefun
import os
import httpx

# 全局变量用于存储配置和数据库实例
_config_context = None
_db_instance = None

def get_down_url_config():
    config_url = os.environ.get('CONFIG_URL')
    if config_url:
        try:
            response = httpx.get(config_url)
            response.raise_for_status()
            print("已读配置文件内容")
            return response.content
        except httpx.HTTPError as e:
            print(f"下载配置文件时发生错误: {e}")
            return False

    else:
        print("未检测到 CONFIG_URL 环境变量，跳过配置文件下载")
        return False


def get_db():
    global _config_context, _db_instance
    
    if _db_instance is None:
        _config_context = get_down_url_config()
        if _config_context:
            _db_instance = apiDB.apiDB(_config_context)
        else:
            api_file_path = os.path.join(os.path.dirname(__file__), './api.yaml')
            print("加载配置文件", _config_context)
            _config_context = pyefun.读入文本(api_file_path)
            _db_instance = apiDB.apiDB(_config_context)
    
    return _db_instance

# 导出 db 实例
db = get_db()
