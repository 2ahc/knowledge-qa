"""管理后台接口（仅管理员）：全局用量统计、任务队列监控。"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db import get_db
from app.models.chat import Message
from app.models.kb import Chunk, Document, KnowledgeBase
from app.models.task import Task
from app.models.user import User

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    """全局概览统计：规模（用户/库/文档/切片）、用量（提问数/Token 数）、
    质量（平均时延）、近 14 天提问趋势、切片数最多的文档。"""
    user_count = db.scalar(select(func.count(User.id))) or 0
    kb_count = db.scalar(select(func.count(KnowledgeBase.id))) or 0
    doc_count = db.scalar(select(func.count(Document.id))) or 0
    chunk_count = db.scalar(select(func.count(Chunk.id))) or 0
    question_count = db.scalar(
        select(func.count(Message.id)).where(Message.role == "user")
    ) or 0
    answer_count = db.scalar(
        select(func.count(Message.id)).where(Message.role == "assistant")
    ) or 0
    prompt_tokens = db.scalar(select(func.coalesce(func.sum(Message.prompt_tokens), 0))) or 0
    completion_tokens = db.scalar(select(func.coalesce(func.sum(Message.completion_tokens), 0))) or 0
    avg_latency = db.scalar(
        select(func.coalesce(func.avg(Message.latency_ms), 0)).where(Message.role == "assistant")
    ) or 0

    # 近 14 天每日提问量（供前端画趋势图）
    day = func.to_char(Message.created_at, "YYYY-MM-DD")
    rows = db.execute(
        select(day.label("d"), func.count(Message.id))
        .where(Message.role == "user")
        .group_by(day)
        .order_by(day.desc())
        .limit(14)
    ).all()
    daily = [{"date": d, "questions": n} for d, n in reversed(rows)]

    # 切片数最多的 5 个文档（反映哪些文档贡献了最多检索内容）
    top_docs = db.execute(
        select(Document.filename, Document.chunk_count, Document.status)
        .order_by(Document.chunk_count.desc())
        .limit(5)
    ).all()

    return {
        "user_count": user_count,
        "kb_count": kb_count,
        "doc_count": doc_count,
        "chunk_count": chunk_count,
        "question_count": question_count,
        "answer_count": answer_count,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "avg_latency_ms": round(float(avg_latency)),
        "daily_questions": daily,
        "top_documents": [
            {"filename": f, "chunk_count": c, "status": s} for f, c, s in top_docs
        ],
    }


@router.get("/tasks")
def list_tasks(limit: int = 50, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    """任务队列监控：最近的任务及其状态/错误/重试次数（排查异步问题用）。"""
    stmt = select(Task).order_by(Task.created_at.desc()).limit(min(limit, 200))
    tasks = db.scalars(stmt).all()
    return [
        {
            "id": str(t.id),
            "kind": t.kind.value,
            "status": t.status.value,
            "error": t.error,
            "attempts": t.attempts,
            "payload": t.payload,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }
        for t in tasks
    ]
