# 认证相关的请求/响应模型。
from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    """登录/刷新返回的双令牌。"""

    access_token: str  # 短期访问令牌，携带在请求头
    refresh_token: str  # 长期刷新令牌，仅用于换新
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    """注册入参。注意：没有 role 字段——注册只能产生普通用户，
    角色由服务端固定写死，客户端传什么都无效（防自我提权）。"""

    # \w 为 Unicode 单词字符：字母/数字/下划线/中文，天然排除空格与标点
    username: str = Field(min_length=2, max_length=20, pattern=r"^\w+$")
    password: str = Field(min_length=6, max_length=64)
    display_name: str | None = Field(default=None, max_length=30)


class RefreshRequest(BaseModel):
    refresh_token: str


class MessageResponse(BaseModel):
    message: str
