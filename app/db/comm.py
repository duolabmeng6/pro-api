import os
import pytz
from datetime import datetime

from app.api_data import db

# 检查路径带有 ./的话转换为当前文件的目录 然后取父目录
DB_PATH = db.config_server.get("db_path", "")
if DB_PATH.index("./"):
    # 把./转换为绝对路径
    当前文件路径 = os.path.abspath(__file__)
    # 取父目录
    父目录 = os.path.dirname(当前文件路径)
    父目录 = os.path.dirname(父目录) + "/"
    # 替换./为父目录
    DB_PATH = DB_PATH.replace("./", 父目录)

# 定义全局变量
if DB_PATH == "":
    print("没有配置数据库")
else:
    print("数据库路径", DB_PATH)

# 添加时区设置
TIMEZONE = pytz.timezone('Asia/Shanghai')  # 设置为您所在的时区，例如：上海

def get_current_time():
    """获取当前时间，考虑时区"""
    return datetime.now(TIMEZONE)

def convert_to_local_time(db_time):
    """将数据库时间转换为本地时间"""
    if db_time.tzinfo is None:
        db_time = pytz.UTC.localize(db_time)
    return db_time.astimezone(TIMEZONE)