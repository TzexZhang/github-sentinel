"""
数据库基础模块，负责定义数据库模型的基础类。
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类，集中保存全部 ORM 模型元数据。"""

    # 所有 ORM 模型共享同一个 metadata，启动时据此创建 SQLite 表结构。
    pass
