"""测试公共夹具。

测试运行在专用数据库上（同一台服务器，库名后缀 _test）。
表结构用 Base.metadata.create_all 直接创建 —— 迁移脚本的正确性
由 Alembic 迁移另行保证，不在单测范围内。
"""
import os
import uuid

os.environ["RUN_WORKER"] = "false"  # 测试中绝不启动内嵌 worker，避免干扰
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://kqa:kqa_pass@127.0.0.1:5432/knowledge_qa")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base, get_db
import app.models  # noqa: F401  导入以注册全部模型

TEST_DB_URL = settings.database_url.rsplit("/", 1)[0] + "/knowledge_qa_test"

engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _create_extensions_and_tables() -> None:
    """先建扩展（pgvector/pg_trgm），再清空重建全部表。"""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    _create_extensions_and_tables()
    # 把全局 SessionLocal 替换成测试库的（聊天 SSE 生成器内部会自己建 Session，
    # 不替换就会连到正式库）
    import app.db as app_db_module

    app_db_module.SessionLocal = TestingSessionLocal
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """每个用例一个干净的数据库：先清空全部表，再给出新 Session。"""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users, knowledge_bases, kb_members, documents, chunks, "
                          "conversations, messages, tasks, eval_datasets, eval_runs CASCADE"))
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    """FastAPI 测试客户端：get_db 依赖被覆盖为同一个测试 Session。"""
    from app.main import app

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_user(db, username="alice", password="pass123456", role="user", display_name=None, is_active=True):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name or username,
        role=UserRole(role),
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(client, username, password="pass123456") -> dict:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
