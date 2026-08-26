# 数据库会话管理：全局引擎 + 请求级 Session。
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


# pool_pre_ping：取连接前先探活，避免使用已被数据库断开的失效连接
engine = create_engine(settings.database_url, pool_pre_ping=True)
# autoflush=False：查询前不自动 flush，避免意外的提前写入
# expire_on_commit=False：commit 后对象属性仍可访问（适合 commit 后继续序列化返回）
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个独立 Session，请求结束自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
