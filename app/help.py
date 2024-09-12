import os
from dotenv import load_dotenv


def load_env():
    # 获取当前脚本文件的绝对路径
    current_script_path = os.path.abspath(__file__)
    # 获取当前脚本所在目录的路径
    current_dir = os.path.dirname(current_script_path)
    # 构建.env文件的绝对路径
    env_path = os.path.join(current_dir,  '.env')
    # 加载.env文件中的环境变量
    load_dotenv(dotenv_path=env_path)
    return os.environ