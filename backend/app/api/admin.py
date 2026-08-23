"""Admin-only endpoints: usage stats, task monitor."""
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

    # per-day question counts for the last 14 days
    day = func.to_char(Message.created_at, "YYYY-MM-DD")
    rows = db.execute(
        select(day.label("d"), func.count(Message.id))
        .where(Message.role == "user")
        .group_by(day)
        .order_by(day.desc())
        .limit(14)
    ).all()
    daily = [{"date": d, "questions": n} for d, n in reversed(rows)]

    # top documents by chunk count
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
