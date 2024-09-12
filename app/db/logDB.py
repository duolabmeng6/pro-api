import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import OperationalError, SQLAlchemyError, IntegrityError
import datetime
import uuid
import hashlib
from dataclasses import dataclass

from app.db.reqCache import ReqCache
from app.db.reqLogs import ReqLog

from app.db.comm import db, DB_PATH

Base = declarative_base()


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

    def _generate_md5(self, data):
        return hashlib.md5(data.encode('utf-8')).hexdigest()

    def insert_req_log(self, req_id, service_provider, token, model, prompt, completion, quota, uri, request_data,
                       response_data):
        session = self.Session()
        try:
            md5 = self._generate_md5(request_data)
            new_log = ReqLog(
                req_id=req_id,
                service_provider=service_provider,
                token=token,
                model=model,
                prompt=prompt,
                completion=completion,
                quota=quota,
                uri=uri,
                request_data=request_data,
                response_data=response_data,
                status='completed',
                md5=md5
            )
            session.add(new_log)
            session.commit()
            return req_id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def update_req_log(self, req_id, prompt, completion, quota, response_data, api_status, api_error):
        session = self.Session()
        try:
            log = session.query(ReqLog).filter_by(req_id=req_id).first()
            if log:
                log.prompt = prompt
                log.completion = completion
                log.quota = quota
                log.response_data = response_data
                log.status = 'completed'
                log.api_status = api_status
                log.api_error = api_error
                session.commit()
            else:
                raise ValueError(f"未找到请求ID为 {req_id} 的日志")
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_log_by_md5(self, md5):
        session = self.Session()
        try:
            log = session.query(ReqLog).filter_by(md5=md5, api_status='200').first()
            return log if log else None
        except Exception as e:
            raise e
        finally:
            session.close()


class CacheManager:
    def __init__(self):
        self.engine = create_engine(DB_PATH)
        self.Session = sessionmaker(bind=self.engine)
        self.sync_table_structure()

    def sync_table_structure(self):
        Base.metadata.create_all(self.engine)

    def add_to_cache(self, md5, req, resp):
        session = self.Session()
        try:
            existing_cache = session.query(ReqCache).filter_by(md5=md5).first()
            if existing_cache:
                # 如果缓存已存在，更新它
                existing_cache.req = req
                existing_cache.resp = resp
                existing_cache.hit_count = 0  # 重置命中次数
            else:
                # 如果缓存不存在，创建新的缓存项
                new_cache = ReqCache(md5=md5, req=req, resp=resp)
                session.add(new_cache)
            session.commit()
            # print(f"缓存已{'更新' if existing_cache else '添加'}")
        except Exception as e:
            session.rollback()
            print(f"添加或更新缓存时出错: {str(e)}")
            raise e
        finally:
            session.close()

    def get_from_cache(self, md5):
        session = self.Session()
        try:
            cache = session.query(ReqCache).filter_by(md5=md5).first()
            if cache:
                cache.hit_count += 1
                session.commit()
                return CacheData(md5=cache.md5, req=cache.req, resp=cache.resp, hit_count=cache.hit_count,
                                 created_at=cache.created_at, updated_at=cache.updated_at)
            return None
        except Exception as e:
            raise e
        finally:
            session.close()

    def update_cache_hit_count(self, md5):
        session = self.Session()
        try:
            cache = session.query(ReqCache).filter_by(md5=md5).first()
            if cache:
                cache.hit_count += 1
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()


@dataclass
class CacheData:
    md5: str
    req: str
    resp: str
    hit_count: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


if __name__ == '__main__':
    logger = RequestLogger()
    cache_manager = CacheManager()

    # 生成请求ID和测试数据
    req_id = str(uuid.uuid4())
    request_data = '{"messages": [{"role": "user", "content": "Python的优点是什么？"}]}'
    md5 = logger._generate_md5(request_data)

    # 插入日志
    logger.insert_req_log(
        req_id=req_id,
        service_provider='OpenAI',
        token='sk-testkey123',
        model='gpt-3.5-turbo',
        prompt=15,
        completion=50,
        quota=0.003,
        uri='https://api.openai.com/v1/chat/completions',
        request_data=request_data,
        response_data='{"choices": [{"message": {"content": "Python的主要优点包括：简洁易读的语法、丰富的库和框架、跨平台兼容性、强大的社区支持等。"}}]}',
    )
    print(f"已插入新的请求日志，ID: {req_id}")

    # 更新日志
    logger.update_req_log(
        req_id=req_id,
        prompt=15,
        completion=50,
        quota=0.003,
        response_data='{"choices": [{"message": {"content": "Python的主要优点包括：简洁易读的语法、丰富的库和框架、跨平台兼容性、强大的社区支持等。"}}]}',
        api_status='200',
        api_error='',
    )
    print(f"已更新请求日志，ID: {req_id}")

    # 根据MD5查询日志
    log = logger.get_log_by_md5(md5)
    if log:
        print(f"成功找到匹配的日志记录，请求ID: {log.req_id}", log.response_data)
    else:
        print("未找到匹配的日志记录")

    # 测试缓存功能
    cache_md5 = hashlib.md5("测试缓存请求".encode('utf-8')).hexdigest()
    cache_manager.add_to_cache(cache_md5, "测试缓存请求", "测试缓存响应")
    print("已添加缓存")

    cached_data = cache_manager.get_from_cache(cache_md5)
    if cached_data:
        print(f"成功从缓存中获取数据：{cached_data.resp}")
        print(f"缓存命中次数：{cached_data.hit_count}")
    else:
        print("未找到缓存数据")

    # 测试重复添加相同的缓存项
    cache_manager.add_to_cache(cache_md5, "测试缓存请求（更新）", "测试缓存响应（更新）")
    updated_cache = cache_manager.get_from_cache(cache_md5)
    if updated_cache:
        print(f"更新后的缓存数据：{updated_cache.resp}")
        print(f"更新后的命中次数：{updated_cache.hit_count}")
        print(f"更新后的命中次数：{updated_cache.updated_at}")
    else:
        print("未找到更新后的缓存数据")
