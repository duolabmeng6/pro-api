import app.apiDB as apiDB
import pyefun
import os
import httpx

# 全局变量用于存储配置和数据库实例
_config_context = None
_db_instance = None

config_url = os.environ.get('config_url')
secret_key = os.environ.get('secret_key', "")

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64


def 监视配置(文件路径, 修改回调fn):
    print(f"创建监视配置{文件路径}")
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    # 监视配置文件变化的事件处理器
    class ConfigFileHandler(FileSystemEventHandler):
        def __init__(self, callback):
            self.callback = callback

        def on_modified(self, event):
            if event.src_path.endswith('api.yaml'):
                print("配置文件已更改，重新加载...")
                self.callback()

    observer = Observer()
    handler = ConfigFileHandler(修改回调fn)
    observer.schedule(handler, path=os.path.dirname(文件路径), recursive=False)
    observer.start()
    return observer




def decrypt_aes_ecb(encrypted_text, key):
    # 将密钥转换为bytes并填充到16字节
    key = key.encode('utf-8')
    key = key.ljust(16, b'\0')[:16]

    # 解码Base64编码的加密文本
    ciphertext = base64.b64decode(encrypted_text)

    # 创建AES-ECB解密器
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()

    # 解密
    padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    # 移除PKCS7填充
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

    return plaintext.decode('utf-8')


def get_db():
    global _config_context, _db_instance

    if _db_instance is None:
        _config_context = get_down_url_config()
        if _config_context:
            _db_instance = apiDB.apiDB(_config_context)
        else:
            api_file_path = os.path.join(os.path.dirname(__file__), './api.yaml')
            print("加载本地配置文件")
            _config_context = pyefun.读入文本(api_file_path)
            _db_instance = apiDB.apiDB(_config_context)

        print(f"配置文件加载状态: {'成功' if _config_context else '失败'}")

    return _db_instance


def reload_db():
    global _config_context, _db_instance
    _db_instance = None
    if _db_instance is None:
        _config_context = get_down_url_config()
        if _config_context:
            _db_instance = apiDB.apiDB(_config_context)
        else:
            api_file_path = os.path.join(os.path.dirname(__file__), './api.yaml')
            print("加载本地配置文件")
            _config_context = pyefun.读入文本(api_file_path)
            _db_instance = apiDB.apiDB(_config_context)
        print(f"配置文件加载状态: {'成功' if _config_context else '失败'}")
    return _db_instance


def get_down_url_config():
    global config_url, secret_key
    config_url = os.environ.get('config_url', "")
    secret_key = os.environ.get('secret_key', "")
    print(f"config_url: {config_url}")
    if config_url:
        try:
            print("下载", config_url)
            response = httpx.get(config_url)
            response.raise_for_status()
            print("已读配置文件内容")
            content = response.content
            if secret_key:
                content = decrypt_aes_ecb(content, secret_key)
            return content
        except httpx.HTTPError as e:
            print(f"下载配置文件时发生错误: {e}")
            return False

    else:
        print("未检测到 config_url 环境变量，跳过配置文件下载")
        return False


# 导出 db 实例
db = get_db()


# 使用示例
if __name__ == "__main__":
    secret_key = "666666"  # 在实际应用中，请使用更安全的方式存储和管理密钥
    encrypted = "xjWq4K5Bl4J5nOkPd6a5uA=="
    decrypted = decrypt_aes_ecb(encrypted, secret_key)
    print(f"解密后: {decrypted}")

    print(get_down_url_config())
