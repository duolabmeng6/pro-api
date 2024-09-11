import logging
from logging.handlers import RotatingFileHandler
import os
from app.api_data import db

save_log_file = db.config_server.get("save_log_file")

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)



# 创建控制台日志输出
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# 设置日志格式

console_handler.setFormatter(formatter)

# 获取 FastAPI logger 实例
logger = logging.getLogger("fastapi")
logger.setLevel(logging.INFO)
logger.addHandler(console_handler)


if save_log_file:
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = os.path.join(log_dir, "app.log")
    # 创建 RotatingFileHandler，限制日志文件大小为5MB，最多保留3个文件
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


# 禁止重复日志
logger.propagate = False


import traceback
import contextlib

@contextlib.asynccontextmanager
async def async_error_handling(error_message="发生错误"):
    try:
        yield
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"{error_message}:\n%s", error_traceback)
        raise

# # 使用方法
# async def some_async_function():
#     async with async_error_handling("在异步函数中发生错误"):
#         # 异步代码
#         await some_async_operation()

@contextlib.contextmanager
def error_handling(error_message="发生错误"):
    try:
        yield
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"{error_message}:\n%s", error_traceback)
        raise