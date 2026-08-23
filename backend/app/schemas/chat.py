import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.chat import MessageRole


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    kb_ids: list[uuid.UUID] = Field(min_length=1)
    conversation_id: uuid.UUID | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    kb_ids: list
    created_at: datetime
    message_count: int = 0


class ConversationCreate(BaseModel):
    title: str = ""
    kb_ids: list[uuid.UUID] = []


class ConversationUpdate(BaseModel):
    title: str | None = None
    kb_ids: list[uuid.UUID] | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: MessageRole
    content: str
    citations: list = []
    latency_ms: int = 0
    created_at: datetime
