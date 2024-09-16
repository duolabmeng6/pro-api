import datetime
import os
import random
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, inspect, text, or_, func
from sqlalchemy.orm import declarative_base, sessionmaker, class_mapper
from sqlalchemy.exc import OperationalError, SQLAlchemyError, IntegrityError
import uuid
import hashlib
from app.db.comm import db, DB_PATH, get_current_time, TIMEZONE

Base = declarative_base()


class ReqLog(Base):
    __tablename__ = 'req_logs'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    time = Column(DateTime(timezone=True), nullable=False, default=get_current_time, comment='请求时间')
    req_id = Column(String(36), nullable=False, index=True, comment='请求ID')
    service_provider = Column(String(50), nullable=False, comment='服务提供商')
    token = Column(String(100), nullable=False, comment='用户令牌')
    model = Column(String(50), nullable=False, comment='用户请求的模型')
    prompt = Column(Integer, nullable=False, default=0, comment='提示词token数')
    completion = Column(Integer, nullable=False, default=0, comment='完成的内容token数')
    quota = Column(Float, nullable=False, default=0.0, comment='消耗的配额')
    uri = Column(String(255), nullable=False, comment='请求URI')
    request_data = Column(Text, nullable=False, comment='请求数据')
    response_data = Column(Text, nullable=True, comment='响应数据')
    api_status = Column(String(10), nullable=True, comment='api状态码')
    api_error = Column(Text, nullable=True, comment='api错误信息')
    status = Column(String(20), nullable=False, default='pending', comment='请求态')
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow,
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
                    print(f"创建 {table_name}")
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

    def statistics(self):
        session = self.Session()
        try:
            result = session.query(
                ReqLog.model,
                func.sum(ReqLog.prompt).label('total_prompt'),
                func.sum(ReqLog.completion).label('total_completion')
            ).group_by(ReqLog.model).all()

            return [
                {
                    'model': item.model,
                    'prompt': item.total_prompt,
                    'completion': item.total_completion
                }
                for item in result
            ]
        except SQLAlchemyError as e:
            print(f"统计数据时出错: {str(e)}")
            return []
        finally:
            session.close()

    def statistics_model_day(self):
        session = self.Session()
        try:
            # 使用本地时间，并扩大时间范围
            end_date = datetime.datetime.now().date()
            start_date = end_date - datetime.timedelta(days=7)

            print(f"查询时间范围: 从 {start_date} 到 {end_date}")

            # 修改查询，使用between来查询时间范围
            result = session.query(
                func.date(ReqLog.time).label('date'),
                ReqLog.model,
                func.sum(ReqLog.prompt).label('total_prompt'),
                func.sum(ReqLog.completion).label('total_completion')
            ).filter(
                func.date(ReqLog.time).between(start_date, end_date)
            ).group_by(
                func.date(ReqLog.time),
                ReqLog.model
            ).order_by(
                func.date(ReqLog.time)
            ).all()

            print(f"查询结果: {result}")

            # 获取所有唯一的日期和模型
            dates = sorted(set(item.date for item in result))
            models = sorted(set(item.model for item in result))

            print(f"检测到的日期: {dates}")
            print(f"检测到的模型: {models}")

            # 创建一个字典来存储每个日期和模型的数据
            data_dict = {(date, model): {'prompt': 0, 'completion': 0} for date in dates for model in models}

            # 填充实际数据
            for item in result:
                data_dict[(item.date, item.model)] = {
                    'prompt': item.total_prompt,
                    'completion': item.total_completion
                }

            # 构造系列数据
            series = []
            for model in models:
                prompt_data = [data_dict[(date, model)]['prompt'] for date in dates]
                completion_data = [data_dict[(date, model)]['completion'] for date in dates]

                series.extend([
                    {
                        "name": f"{model} 提示词",
                        "type": "line",
                        "data": prompt_data
                    },
                    {
                        "name": f"{model} 生成词",
                        "type": "line",
                        "data": completion_data
                    }
                ])

            # 构造ECharts配置
            echarts_config = {
                "xAxis": {
                    "type": "category",
                    "data": dates  # 日期已经是字符串格式，无需再次格式化
                },
                "yAxis": {
                    "type": "value"
                },
                "series": series,
                "legend": {},
                "tooltip": {
                    "trigger": "axis"
                }
            }

            print(f"生成的ECharts配置: {echarts_config}")

            return echarts_config

        except SQLAlchemyError as e:
            print(f"统计模型每日使用情况时出错: {str(e)}")
            return {}
        finally:
            session.close()

    def insert_random_test_data(self, num_entries=50):
        session = self.Session()
        try:
            # 获取当前日期
            end_date = datetime.datetime.now()
            start_date = end_date - datetime.timedelta(days=7)

            # 定义可能的模型和状态
            models = ['glm-4-flash', 'gpt-3.5-turbo', 'gpt-4']
            statuses = ['success', 'failed', 'pending']

            # 生成随机数据
            for _ in range(num_entries):
                random_date = start_date + datetime.timedelta(
                    seconds=random.randint(0, int((end_date - start_date).total_seconds()))
                )
                random_model = random.choice(models)
                random_status = random.choice(statuses)

                new_log = ReqLog(
                    time=random_date,
                    req_id=str(uuid.uuid4()),
                    service_provider='test_provider',
                    token='test_token',
                    model=random_model,
                    prompt=random.randint(10, 500),
                    completion=random.randint(50, 1000),
                    quota=random.uniform(0.1, 5.0),
                    uri='/test/api',
                    request_data='{"test": "data"}',
                    response_data='{"test": "response"}',
                    api_status='200',
                    api_error=None,
                    status=random_status,
                    md5=hashlib.md5(str(random.random()).encode()).hexdigest()
                )

                session.add(new_log)

            session.commit()
            print(f"成功插入 {num_entries} 条随机测试数据")

        except SQLAlchemyError as e:
            session.rollback()
            print(f"插入随机测试数据时出错: {str(e)}")
        finally:
            session.close()


if __name__ == '__main__':
    logger = RequestLogger()
    #
    # dataList, total = logger.index(keywords="", per_page=10, page=1, order_by="id", order_dir="desc")
    # print(dataList)
    # print(total)
    # for data in dataList:
    #     print(data.req_id)
    #     print(data.time)
    #     print(data.service_provider)
    #     print(data.token)
    #     print(data.model)
    #     print(data.prompt)
    #     print(data.completion)
    #     print(data.quota)
    #     print(data.uri)
    #     print(data.request_data)
    # data = logger.statistics()
    # print(data)
    logger.insert_random_test_data()

    data = logger.statistics_model_day()
    print(data)
