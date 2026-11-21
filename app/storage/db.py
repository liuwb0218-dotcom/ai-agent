# -*- coding: utf-8 -*-
"""数据库连接管理：SQLAlchemy 2.0 + MySQL"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """ORM 声明式基类"""


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,      # 连接前探测，避免 MySQL 8h 超时断连
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI 依赖：请求级数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
