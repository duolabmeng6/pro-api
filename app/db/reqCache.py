import os

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, inspect, text, or_
from sqlalchemy.orm import declarative_base, sessionmaker, class_mapper
from sqlalchemy.exc import OperationalError, SQLAlchemyError, IntegrityError
import datetime
import uuid
import hashlib
from dataclasses import dataclass

from app.db.comm import db, DB_PATH

Base = declarative_base()


class ReqCache(Base):
    __tablename__ = 'req_cache'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow,
                        comment='更新时间')
    md5 = Column(String(32), nullable=False, unique=True, index=True, comment='MD5哈希')
    req = Column(Text, nullable=False, comment='请求数据')
    resp = Column(Text, nullable=False, comment='响应数据')
    hit_count = Column(Integer, nullable=False, default=0, comment='命中次数')

class RequestCacheManager:
    def __init__(self):
        self.engine = create_engine(DB_PATH)
        self.Session = sessionmaker(bind=self.engine)
        self.sync_table_structure()

    def sync_table_structure(self):
        inspector = inspect(self.engine)

        with self.engine.connect() as connection:
            for table_name, table in Base.metadata.tables.items():
                if not inspector.has_table(table_name):
                    table.create(self.engine)
                    print(f"创建表 {table_name}")
                else:
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
            query = session.query(ReqCache)
            if keywords:
                query = query.filter(or_(
                    ReqCache.md5.like(f"%{keywords}%"),
                    ReqCache.req.like(f"%{keywords}%"),
                    ReqCache.resp.like(f"%{keywords}%")
                ))
            
            total = query.count()
            
            if order_dir.lower() == "desc":
                query = query.order_by(getattr(ReqCache, order_by).desc())
            else:
                query = query.order_by(getattr(ReqCache, order_by))
            
            caches = query.offset((page - 1) * per_page).limit(per_page).all()
            return [self.to_dict(cache) for cache in caches], total
        except SQLAlchemyError as e:
            print(f"查询缓存时出错: {str(e)}")
            return [], 0
        finally:
            session.close()

    def insert(self, cache_data):
        session = self.Session()
        try:
            new_cache = ReqCache(**cache_data)
            session.add(new_cache)
            session.commit()
            return new_cache.id
        except SQLAlchemyError as e:
            session.rollback()
            print(f"插入缓存时出错: {str(e)}")
            return None
        finally:
            session.close()

    def find_one(self, cache_id):
        session = self.Session()
        try:
            cache = session.query(ReqCache).filter(ReqCache.id == cache_id).first()
            return self.to_dict(cache)
        except SQLAlchemyError as e:
            print(f"查找缓存时出错: {str(e)}")
            return None
        finally:
            session.close()

    def update(self, cache_data):
        session = self.Session()
        try:
            cache_id = cache_data.pop('id', None)
            if cache_id is None:
                raise ValueError("更新缓存时需要提供id")
            
            session.query(ReqCache).filter(ReqCache.id == cache_id).update(cache_data)
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            print(f"更新缓存时出错: {str(e)}")
            return False
        finally:
            session.close()

    def delete(self, cache_id):
        session = self.Session()
        try:
            cache = session.query(ReqCache).filter(ReqCache.id == cache_id).first()
            if cache:
                session.delete(cache)
                session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            session.rollback()
            print(f"删除缓存时出错: {str(e)}")
            return False
        finally:
            session.close()

    def bulk_delete(self, cache_ids):
        session = self.Session()
        try:
            session.query(ReqCache).filter(ReqCache.id.in_(cache_ids)).delete(synchronize_session=False)
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            print(f"批量删除缓存时出错: {str(e)}")
            return False
        finally:
            session.close()

    def get_by_md5(self, md5):
        session = self.Session()
        try:
            cache = session.query(ReqCache).filter(ReqCache.md5 == md5).first()
            if cache:
                cache.hit_count += 1
                session.commit()
            return self.to_dict(cache)
        except SQLAlchemyError as e:
            print(f"通过MD5获取缓存时出错: {str(e)}")
            return None
        finally:
            session.close()

if __name__ == '__main__':
    cache_manager = RequestCacheManager()
    
    # 测试插入缓存
    cache_id = cache_manager.insert({
        "md5": "test_md5",
        "req": "test_req",
        "resp": "test_resp"
    })
    print(f"插入的缓存ID: {cache_id}")
    
    # 测试查询缓存
    caches, total = cache_manager.index(keywords="", per_page=10, page=1, order_by="id", order_dir="desc")
    print(f"总缓存数: {total}")
    for cache in caches:
        print(cache)
    
    # 测试通过MD5获取缓存
    cache = cache_manager.get_by_md5("test_md5")
    if cache:
        print(f"通过MD5获取的缓存: {cache}")
        print(f"命中次数: {cache['hit_count']}")
    
    # 测试删除缓存
    if cache_id:
        deleted = cache_manager.delete(cache_id)
        print(f"删除缓存结果: {deleted}")
