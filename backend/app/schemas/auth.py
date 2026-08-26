# 认证相关的请求/响应模型。
from pydantic import BaseModel


class TokenPair(BaseModel):
    """登录/刷新返回的双令牌。"""

    access_token: str  # 短期访问令牌，携带在请求头
    refresh_token: str  # 长期刷新令牌，仅用于换新
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class MessageResponse(BaseModel):
    message: str
