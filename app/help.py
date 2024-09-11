import os
from dotenv import load_dotenv


def load_env():
    # 加载.env文件中的环境变量
    load_dotenv(dotenv_path='.env')
    return os.environ