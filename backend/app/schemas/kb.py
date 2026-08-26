# 知识库、成员、文档的请求/响应模型。
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.kb import DocStatus, KbMemberRole, KbVisibility


class KbCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    visibility: KbVisibility = KbVisibility.private


class KbUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    visibility: KbVisibility | None = None


class KbOut(BaseModel):
    """知识库出参：基础信息 + 实时统计（文档数/切片数）。"""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str
    owner_id: uuid.UUID
    visibility: KbVisibility
    embed_model: str
    created_at: datetime
    doc_count: int = 0
    chunk_count: int = 0


class MemberCreate(BaseModel):
    user_id: uuid.UUID
    role: KbMemberRole = KbMemberRole.viewer


class MemberOut(BaseModel):
    user_id: uuid.UUID
    username: str
    display_name: str
    role: KbMemberRole


class DocumentOut(BaseModel):
    """文档出参：前端据此渲染文档列表与索引状态。"""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kb_id: uuid.UUID
    filename: str
    filetype: str
    size_bytes: int
    status: DocStatus
    error: str
    chunk_count: int
    created_by: uuid.UUID
    created_at: datetime
