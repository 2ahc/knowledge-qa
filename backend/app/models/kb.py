# 知识库核心模型：知识库 → 文档 → 切片 三级结构。
# 这是整个 RAG 系统的数据地基：切片(Chunk)携带向量，是检索的最小单元。
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.db import Base

# 向量维度，必须与 embed_model（text-embedding-v4 = 1024 维）保持一致！
# 换向量模型时必须同步改这里并重建数据库。
EMBED_DIM = 1024


class KbVisibility(str, PyEnum):
    """知识库可见性：
    private = 仅创建者可见；
    shared  = 创建者 + 显式添加的成员（见 KbMember）；
    public  = 所有登录用户可见。
    """

    private = "private"
    shared = "shared"
    public = "public"


class KbMemberRole(str, PyEnum):
    """成员角色：editor 可管理文档与成员；viewer 只读（可提问）。"""

    editor = "editor"
    viewer = "viewer"


class DocStatus(str, PyEnum):
    """文档索引状态机：pending(排队) → parsing(解析中) → embedding(向量化中) → done；
    任意阶段失败转为 failed，可调用重建索引接口重新排队。"""

    pending = "pending"
    parsing = "parsing"
    embedding = "embedding"
    done = "done"
    failed = "failed"


class KnowledgeBase(Base):
    """知识库：文档的容器，权限控制的主体。"""

    __tablename__ = "knowledge_bases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    visibility: Mapped[KbVisibility] = mapped_column(
        Enum(KbVisibility, name="kb_visibility"), default=KbVisibility.private
    )
    # 记录建库时使用的向量模型：不同模型的向量不可混用，
    # 换模型后需要重建该库的全部文档索引
    embed_model: Mapped[str] = mapped_column(String(64), default=settings.embed_model)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KbMember(Base):
    """知识库成员表（联合主键：一个用户在一个库里只有一条记录）。
    仅在 visibility=shared 时生效。删除库/用户时级联清理。"""

    __tablename__ = "kb_members"

    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[KbMemberRole] = mapped_column(
        Enum(KbMemberRole, name="kb_member_role"), default=KbMemberRole.viewer
    )


class Document(Base):
    """上传的原始文档。上传即建记录并入队异步索引，前端轮询 status 展示进度。"""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))  # 原始文件名，引用溯源时展示
    # 相对上传根目录的路径（如 "kb_id/doc_id.md"），宿主机与容器内均可解析
    stored_path: Mapped[str] = mapped_column(String(512), default="")
    filetype: Mapped[str] = mapped_column(String(16), default="")  # 扩展名，决定用哪个解析器
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[DocStatus] = mapped_column(Enum(DocStatus, name="doc_status"), default=DocStatus.pending)
    error: Mapped[str] = mapped_column(Text, default="")  # 失败原因，前端直接展示
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)  # 索引成功后的切片数
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Chunk(Base):
    """文本切片：检索与引用的最小单元。

    每个切片 = 一段正文 + 它的向量 + 出处元信息（页码/章节/工作表）。
    问答时检索命中的就是切片，引用卡片展示的也是切片内容。
    """

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    # 冗余 kb_id：检索时直接按库过滤，避免 join 文档表
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)  # 切片正文
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    # 出处元信息，如 {"page": 3}、{"section": "员工福利"}、{"sheet": "Sheet1"}
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    # pgvector 向量列；数据库层建有 HNSW 余弦相似度索引（见迁移脚本）
    embedding = mapped_column(Vector(EMBED_DIM))
