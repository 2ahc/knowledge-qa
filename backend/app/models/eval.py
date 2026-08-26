# 评测模型：评测集（题目）与评测运行（一次打分过程及结果）。
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.task import TaskStatus


class EvalDataset(Base):
    """评测集：一组评测题目。

    每个 item 形如：
      {"question": "...", "expect_keywords": ["2020"], "expect_doc": "公司介绍"}
    """

    __tablename__ = "eval_datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    items: Mapped[list] = mapped_column(JSONB, default=list)  # 评测题目列表
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvalRun(Base):
    """一次评测运行：对某个数据集在指定知识库上跑完整评测并汇总指标。"""

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_datasets.id", ondelete="CASCADE"), index=True
    )
    # 运行配置：{"kb_ids": [...], "top_k": 6}
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[TaskStatus] = mapped_column(default=TaskStatus.queued)
    # 汇总指标：检索命中率、关键词命中率、忠实性/相关性均分等
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    # 逐题明细：每题的检索结果、回答、得分
    results: Mapped[list] = mapped_column(JSONB, default=list)
    error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
