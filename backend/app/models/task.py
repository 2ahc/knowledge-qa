# 任务队列模型：基于数据库实现的异步任务（无需 Redis）。
# worker 用 SELECT ... FOR UPDATE SKIP LOCKED 抢占任务，天然支持多实例并行消费。
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TaskKind(str, PyEnum):
    """任务类型：文档索引 / 文档重建索引 / 评测运行。"""

    document_index = "document.index"
    document_reindex = "document.reindex"
    eval_run = "eval.run"


class TaskStatus(str, PyEnum):
    """任务状态：排队 → 运行中 → 完成/失败（失败可按策略重入队重试）。"""

    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[TaskKind] = mapped_column(Enum(TaskKind, name="task_kind"), index=True)
    # 任务参数，如 {"document_id": "..."} 或 {"eval_run_id": "..."}
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, name="task_status"), default=TaskStatus.queued)
    error: Mapped[str] = mapped_column(Text, default="")  # 最近一次失败的错误信息
    attempts: Mapped[int] = mapped_column(Integer, default=0)  # 已尝试次数（超过上限不再重试）
    # 心跳时间：running 中的任务定期更新，超时未更新视为僵死，由 recover_stale 回收
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
