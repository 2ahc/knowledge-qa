# 基于数据库的任务队列（无需 Redis/Celery）。
# 核心机制：worker 用 SELECT ... FOR UPDATE SKIP LOCKED 抢任务，
# 多个 worker 并行消费也不会重复领取同一条任务。
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models.task import Task, TaskKind, TaskStatus

logger = logging.getLogger(__name__)


def enqueue(db: Session, kind: TaskKind, payload: dict) -> Task:
    """入队：创建一条排队中的任务。业务方（上传/重建索引/发起评测）调用。"""
    task = Task(kind=kind, payload=payload)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def claim_next(db: Session) -> Task | None:
    """原子地领取一条排队任务（先进先出）。

    with_for_update(skip_locked=True) 是关键：
    - FOR UPDATE 锁住该行，其他事务读不到中间状态；
    - SKIP LOCKED 让并发 worker 跳过已被锁的行，直接拿下一条。
    两者合起来实现"每条任务只被一个 worker 领走一次"。
    """
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
    task.heartbeat_at = datetime.now(timezone.utc)  # 开始心跳，供僵死回收判断
    db.commit()
    db.refresh(task)
    return task


def heartbeat(db: Session, task_id: uuid.UUID) -> None:
    """更新心跳时间：长任务定期调用，证明自己还活着、不是僵死任务。"""
    db.execute(update(Task).where(Task.id == task_id).values(heartbeat_at=datetime.now(timezone.utc)))
    db.commit()


class Heartbeat:
    """长任务心跳节流器：在循环里随时调 beat()，
    但只有距上次心跳超过 interval 秒才真正写库，避免高频 UPDATE。

    用法（见 indexing.py / eval.py）：
        hb = Heartbeat(db, task_id)
        for ... : hb.beat()
    """

    def __init__(self, db: Session, task_id: uuid.UUID | None, interval: float = 60.0):
        self._db = db
        self._task_id = task_id
        self._interval = interval
        self._last = time.monotonic()
        if task_id is not None:
            heartbeat(db, task_id)  # 开局先跳一次，延长僵死判定的起点

    def beat(self) -> None:
        if self._task_id is None:
            return
        now = time.monotonic()
        if now - self._last >= self._interval:
            heartbeat(self._db, self._task_id)
            self._last = now


def mark_done(db: Session, task_id: uuid.UUID) -> None:
    """标记任务成功完成。"""
    db.execute(update(Task).where(Task.id == task_id).values(status=TaskStatus.done, error=""))
    db.commit()


def mark_failed(db: Session, task_id: uuid.UUID, error: str, requeue: bool = False) -> None:
    """标记任务失败；若允许重试且未超过 3 次，则重新入队。"""
    task = db.get(Task, task_id)
    if task is None:
        return
    task.error = error[:2000]
    if requeue and task.attempts < 3:
        task.status = TaskStatus.queued  # 回到队列等待再次被领取
    else:
        task.status = TaskStatus.failed
    db.commit()


def recover_stale(db: Session) -> int:
    """回收僵死任务：心跳超时（默认 30 分钟）的 running 任务，
    通常意味着 worker 崩溃了，重新放回队列让其他 worker 接手。"""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.task_stale_minutes)
    stmt = (
        update(Task)
        .where(Task.status == TaskStatus.running, Task.heartbeat_at < cutoff)
        .values(status=TaskStatus.queued)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount or 0
