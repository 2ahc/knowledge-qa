# 评测相关的请求/响应模型。
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvalDatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    items: list[dict] = Field(min_length=1)
    # 每条评测项结构：{"question": 问题, "expect_keywords": [期望关键词], "expect_doc": 期望文档名}


class EvalDatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    items: list
    created_by: uuid.UUID
    created_at: datetime


class EvalRunCreate(BaseModel):
    dataset_id: uuid.UUID
    kb_ids: list[uuid.UUID] = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class EvalRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    dataset_id: uuid.UUID
    config: dict
    status: str
    metrics: dict
    error: str
    created_by: uuid.UUID
    created_at: datetime
