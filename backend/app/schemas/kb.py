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
