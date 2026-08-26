# 会话与消息模型：多轮问答的持久化载体。
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MessageRole(str, PyEnum):
    """消息角色：user=用户提问，assistant=AI 回答。"""

    user = "user"
    assistant = "assistant"


class Conversation(Base):
    """一次会话（对话窗口）。同一会话内的消息构成多轮上下文。"""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(Text, default="")  # 默认取首条提问作为标题
    # 本会话使用的知识库 ID 列表（问答时按这些库检索）
    kb_ids: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    """单条消息。assistant 消息额外记录引用来源与用量指标。"""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, name="message_role"))
    content: Mapped[str] = mapped_column(Text, default="")  # 消息正文
    # 引用来源列表：命中的切片信息（文档名/位置/内容/得分），前端渲染引用卡片
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)  # 输入 token 数（计费/统计）
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)  # 输出 token 数
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)  # 本次生成耗时
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
