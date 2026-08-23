"""Test fixtures.

Tests run against a dedicated database (same server, name suffixed with _test).
Tables are created via Base.metadata.create_all — schema correctness is covered
by Alembic migrations separately.
"""
import os
import uuid

os.environ["RUN_WORKER"] = "false"  # never start the embedded worker in tests
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://kqa:kqa_pass@127.0.0.1:5432/knowledge_qa")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base, get_db
import app.models  # noqa: F401  register models

TEST_DB_URL = settings.database_url.rsplit("/", 1)[0] + "/knowledge_qa_test"

engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _create_extensions_and_tables() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    _create_extensions_and_tables()
    # route every SessionLocal() call (e.g. the chat SSE generator) to the test DB
    import app.db as app_db_module

    app_db_module.SessionLocal = TestingSessionLocal
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
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
