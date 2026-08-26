# 问答与会话的请求/响应模型。
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.chat import MessageRole


class ChatRequest(BaseModel):
    """提问入参：问题 + 至少一个知识库 + 可选的会话（续聊）。"""

    question: str = Field(min_length=1, max_length=2000)
    kb_ids: list[uuid.UUID] = Field(min_length=1)  # 在哪些知识库里检索
    conversation_id: uuid.UUID | None = None  # 为空则新建会话


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
