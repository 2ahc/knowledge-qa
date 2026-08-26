# 用户模型：系统账号、角色与启用状态。
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserRole(str, PyEnum):
    """系统级角色：admin 可管理用户与查看全局统计；user 为普通用户。"""

    admin = "admin"
    user = "user"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # 登录名，全局唯一
    password_hash: Mapped[str] = mapped_column(String(128))  # bcrypt 哈希，不存明文
    display_name: Mapped[str] = mapped_column(String(64), default="")  # 界面展示昵称
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.user)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # 停用后无法登录
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
