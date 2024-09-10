import os

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, inspect, text, or_
from sqlalchemy.orm import declarative_base, sessionmaker, class_mapper
from sqlalchemy.exc import OperationalError, SQLAlchemyError, IntegrityError
import datetime
import uuid
import hashlib
from dataclasses import dataclass
from app.apiDB import apiDB

db = apiDB(os.path.join(os.path.dirname(__file__), '../api.yaml'))
# 定义全局变量
DB_PATH = db.config_server.get("db_path", "")
if DB_PATH == "":
    print("没有配置数据库")
    exit()

Base = declarative_base()


class ReqLog(Base):
    __tablename__ = 'req_logs'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    time = Column(DateTime, nullable=False, default=datetime.datetime.utcnow, comment='请求时间')
    req_id = Column(String(36), nullable=False, index=True, comment='请求ID')
    service_provider = Column(String(50), nullable=False, comment='服务提供商')
    token = Column(String(100), nullable=False, comment='用户令牌')
    model = Column(String(50), nullable=False, comment='使用的模型')
    prompt = Column(Integer, nullable=False, default=0, comment='提示词token数')
    completion = Column(Integer, nullable=False, default=0, comment='完成的内容token数')
    quota = Column(Float, nullable=False, default=0.0, comment='消耗的配额')
    uri = Column(String(255), nullable=False, comment='请求URI')
    request_data = Column(Text, nullable=False, comment='请求数据')
    response_data = Column(Text, nullable=True, comment='响应数据')
    api_status = Column(String(10), nullable=True, comment='api状态码')
    api_error = Column(Text, nullable=True, comment='api错误信息')
    status = Column(String(20), nullable=False, default='pending', comment='请求态')
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow,
                        comment='更新时间')
    md5 = Column(String(32), nullable=False, index=True, comment='MD5哈希，于缓存')


class RequestLogger:
    def __init__(self):
        self.engine = create_engine(DB_PATH)
        self.Session = sessionmaker(bind=self.engine)
        self.sync_table_structure()

    def sync_table_structure(self):
        inspector = inspect(self.engine)

        with self.engine.connect() as connection:
            for table_name, table in Base.metadata.tables.items():
                if not inspector.has_table(table_name):
                    # 如果表不存在，创建它
                    table.create(self.engine)
                    print(f"创建表 {table_name}")
                else:
                    # 如果表存在，检查并添加缺失的列
                    existing_columns = inspector.get_columns(table_name)
                    existing_column_names = {col['name'] for col in existing_columns}

                    for column in table.columns:
                        if column.name not in existing_column_names:
                            column_type = column.type.compile(self.engine.dialect)
                            try:
                                sql = text(f'ALTER TABLE {table_name} ADD COLUMN {column.name} {column_type}')
                                connection.execute(sql)
                                connection.commit()
                                print(f"向表 {table_name} 添加列 {column.name}")
                            except SQLAlchemyError as e:
                                print(f"向表 {table_name} 添加列 {column.name} 时出错: {str(e)}")
                                connection.rollback()

    def to_dict(self, obj):
        """将SQLAlchemy对象转换为字典"""
        if obj is None:
            return None
        result = {}
        for key in class_mapper(obj.__class__).columns.keys():
            value = getattr(obj, key)
            if isinstance(value, (datetime.date, datetime.datetime)):
                value = value.isoformat()
            result[key] = value
        return result

    def index(self, keywords, per_page, page, order_by="id", order_dir="desc"):
        session = self.Session()
        try:
            query = session.query(ReqLog)
            if keywords:
                query = query.filter(or_(
                    ReqLog.req_id.like(f"%{keywords}%"),
                    ReqLog.service_provider.like(f"%{keywords}%"),
                    ReqLog.token.like(f"%{keywords}%"),
                    ReqLog.model.like(f"%{keywords}%"),
                    ReqLog.uri.like(f"%{keywords}%"),
                    ReqLog.status.like(f"%{keywords}%")
                ))
            
            total = query.count()
            
            if order_dir.lower() == "desc":
                query = query.order_by(getattr(ReqLog, order_by).desc())
            else:
                query = query.order_by(getattr(ReqLog, order_by))
            
            logs = query.offset((page - 1) * per_page).limit(per_page).all()
            return [self.to_dict(log) for log in logs], total
        except SQLAlchemyError as e:
            print(f"查询日志时出错: {str(e)}")
            return [], 0
        finally:
            session.close()

    def insert(self, log_data):
        session = self.Session()
        try:
            new_log = ReqLog(**log_data)
            session.add(new_log)
            session.commit()
            return new_log.id
        except SQLAlchemyError as e:
            session.rollback()
            print(f"插入日志时出错: {str(e)}")
            return None
        finally:
            session.close()

    def find_one(self, log_id):
        session = self.Session()
        try:
            log = session.query(ReqLog).filter(ReqLog.id == log_id).first()
            return self.to_dict(log)
        except SQLAlchemyError as e:
            print(f"查找日志时出错: {str(e)}")
            return None
        finally:
            session.close()

    def update(self, log_data):
        session = self.Session()
        try:
            log_id = log_data.pop('id', None)
            if log_id is None:
                raise ValueError("更新日志时需要提供id")
            
            session.query(ReqLog).filter(ReqLog.id == log_id).update(log_data)
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            print(f"更新日志时出错: {str(e)}")
            return False
        finally:
            session.close()

    def delete(self, log_id):
        session = self.Session()
        try:
            log = session.query(ReqLog).filter(ReqLog.id == log_id).first()
            if log:
                session.delete(log)
                session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            session.rollback()
            print(f"删除日志时出错: {str(e)}")
            return False
        finally:
            session.close()

    def bulk_delete(self, log_ids):
        session = self.Session()
        try:
            session.query(ReqLog).filter(ReqLog.id.in_(log_ids)).delete(synchronize_session=False)
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            print(f"批量删除日志时出错: {str(e)}")
            return False
        finally:
            session.close()

if __name__ == '__main__':
    logger = RequestLogger()
    
    dataList, total = logger.index(keywords="", per_page=10, page=1, order_by="id", order_dir="desc")
    print(dataList)
    print(total)
    for data in dataList:
        print(data.req_id)
        print(data.time)
        print(data.service_provider)
        print(data.token)
        print(data.model)
        print(data.prompt)
        print(data.completion)
        print(data.quota)
        print(data.uri)
        print(data.request_data)
        
