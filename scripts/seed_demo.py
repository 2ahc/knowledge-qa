"""Seed demo data: admin user + a public sample knowledge base with one document.

Usage (from backend/):
    uv run python ../scripts/seed_demo.py [--admin-password <pwd>]

Prints the admin credentials. Safe to re-run: existing objects are skipped.
Requires the API server (or worker) to be running afterwards to index the document.
"""
import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models.kb import Document, KbVisibility, KnowledgeBase  # noqa: E402
from app.models.task import TaskKind  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.services import tasks as task_queue  # noqa: E402

SAMPLE_DOC = """# 拾光茶屋员工手册（示例文档）

## 公司简介

拾光茶屋成立于 2020 年，是一家专注于新式茶饮的连锁企业，总部位于杭州。
目前在全国拥有 120 家门店，招牌产品包括珍珠奶茶、黑糖鹿丸鲜奶和芋泥波波奶茶。

## 员工福利

- 五险一金与补充医疗保险
- 带薪年假 10 天起
- 每季度免费饮品券 30 张
- 生日当天免费任选饮品一杯

## 门店运营规范

门店营业时间统一为 09:00 - 22:00。
所有饮品必须在下单后 10 分钟内出品，珍珠类小料每 4 小时更换一次。

## 客服与投诉处理

顾客投诉应在 24 小时内响应。涉及食品安全的投诉须立即上报区域经理。
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin-password", default=None)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        # 1) admin user
        admin = db.scalar(select(User).where(User.username == "admin"))
        if admin is None:
            password = args.admin_password or secrets.token_urlsafe(12)
            admin = User(
                username="admin",
                password_hash=hash_password(password),
                display_name="管理员",
                role=UserRole.admin,
            )
            db.add(admin)
            db.commit()
            print(f"[seed] 管理员已创建: admin / {password}")
        else:
            print("[seed] 管理员 admin 已存在，跳过")

        # 2) demo knowledge base
        kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.name == "示例知识库"))
        if kb is None:
            kb = KnowledgeBase(
                name="示例知识库",
                description="种子示例：员工手册，用于快速体验问答",
                visibility=KbVisibility.public,
                owner_id=admin.id,
            )
            db.add(kb)
            db.commit()
            db.refresh(kb)
            print(f"[seed] 知识库已创建: {kb.name} ({kb.id})")
        else:
            print(f"[seed] 知识库「示例知识库」已存在 ({kb.id})")

        # 3) sample document + index task (idempotent by filename)
        exists = db.scalar(
            select(Document).where(Document.kb_id == kb.id, Document.filename == "员工手册示例.md")
        )
        if exists is None:
            doc = Document(
                kb_id=kb.id,
                filename="员工手册示例.md",
                filetype="md",
                created_by=admin.id,
                status="pending",
            )
            db.add(doc)
            db.flush()
            target_dir = settings.upload_path / str(kb.id)
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"{doc.id}.md"
            target.write_text(SAMPLE_DOC, encoding="utf-8")
            # relative path: resolves on host and inside containers alike
            doc.stored_path = f"{kb.id}/{doc.id}.md"
            doc.size_bytes = target.stat().st_size
            db.commit()
            task_queue.enqueue(db, TaskKind.document_index, {"document_id": str(doc.id)})
            print(f"[seed] 示例文档已创建并入队索引: {doc.filename}")
        else:
            print("[seed] 示例文档已存在，跳过")

        print("[seed] 完成。启动服务后，示例文档将自动完成索引，可直接提问。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
