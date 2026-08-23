"""DB-backed task queue. Worker claims tasks with FOR UPDATE SKIP LOCKED."""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models.task import Task, TaskKind, TaskStatus

logger = logging.getLogger(__name__)


def enqueue(db: Session, kind: TaskKind, payload: dict) -> Task:
    task = Task(kind=kind, payload=payload)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def claim_next(db: Session) -> Task | None:
    stmt = (
        select(Task)
        .where(Task.status == TaskStatus.queued)
        .order_by(Task.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    task = db.scalar(stmt)
    if task is None:
        return None
    task.status = TaskStatus.running
    task.attempts += 1
    task.heartbeat_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task


def heartbeat(db: Session, task_id: uuid.UUID) -> None:
    db.execute(update(Task).where(Task.id == task_id).values(heartbeat_at=datetime.now(timezone.utc)))
    db.commit()


def mark_done(db: Session, task_id: uuid.UUID) -> None:
    db.execute(update(Task).where(Task.id == task_id).values(status=TaskStatus.done, error=""))
    db.commit()


def mark_failed(db: Session, task_id: uuid.UUID, error: str, requeue: bool = False) -> None:
    task = db.get(Task, task_id)
    if task is None:
        return
    task.error = error[:2000]
    if requeue and task.attempts < 3:
        task.status = TaskStatus.queued
    else:
        task.status = TaskStatus.failed
    db.commit()


def recover_stale(db: Session) -> int:
    """Requeue running tasks whose heartbeat went stale (worker crashed)."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.task_stale_minutes)
    stmt = (
        update(Task)
        .where(Task.status == TaskStatus.running, Task.heartbeat_at < cutoff)
        .values(status=TaskStatus.queued)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount or 0
