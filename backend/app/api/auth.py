# 认证接口：登录、刷新令牌、当前用户、登出。
# 采用双令牌模式：access（短期，2 小时）携带在请求头；
# refresh（长期，7 天）仅在 access 过期后用于无感换新。
import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_token, decode_token, verify_password
from app.db import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, MessageResponse, RefreshRequest, TokenPair
from app.schemas.user import UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """登录：校验用户名密码，签发 access + refresh 双令牌。"""
    user = db.scalar(select(User).where(User.username == body.username))
    # 统一报"用户名或密码错误"，不区分两者，避免泄露账号是否存在
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")
    return TokenPair(
        access_token=create_token(user.id, user.role.value, "access"),
        refresh_token=create_token(user.id, user.role.value, "refresh"),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    """用 refresh 令牌换取一对新令牌（refresh 也轮换，降低长期令牌泄露风险）。"""
    try:
        payload = decode_token(body.refresh_token, token_type="refresh")
    except pyjwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"refresh token 无效: {e}")
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已停用")
    return TokenPair(
        access_token=create_token(user.id, user.role.value, "access"),
        refresh_token=create_token(user.id, user.role.value, "refresh"),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", response_model=MessageResponse)
def logout(_: User = Depends(get_current_user)):
    # JWT 无状态：服务端不存会话，"登出"由客户端丢弃令牌实现。
    # 此端点只为 API 对称性存在（前端可统一调用）。
    return MessageResponse(message="已退出登录")
