# 用户相关的请求/响应模型（pydantic schema）。
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole


class UserOut(BaseModel):
    """用户信息出参（不含密码哈希，安全）。"""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    """创建用户入参。"""

    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=64)
    display_name: str = ""
    role: UserRole = UserRole.user


class UserUpdate(BaseModel):
    """更新用户入参：所有字段可选，传哪个改哪个。"""

    display_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6, max_length=64)
