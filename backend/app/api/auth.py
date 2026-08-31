# 认证接口：注册、登录、刷新令牌、当前用户、登出。
# 采用双令牌模式：access（短期，2 小时）携带在请求头；
# refresh（长期，7 天）仅在 access 过期后用于无感换新。
import time
import uuid

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db import get_db
from app.core.deps import get_current_user
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, MessageResponse, RefreshRequest, RegisterRequest, TokenPair
from app.schemas.user import UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 注册限流（进程内，按来源 IP 固定窗口）：开放接口更要防脚本批量刷号
_REGISTER_LIMIT_PER_MINUTE = 5
_register_windows: dict[str, tuple[float, int]] = {}


def _check_register_rate(ip: str) -> None:
    now = time.time()
    window_start, count = _register_windows.get(ip, (now, 0))
    if now - window_start >= 60:
        window_start, count = now, 0
    count += 1
    _register_windows[ip] = (window_start, count)
    if count > _REGISTER_LIMIT_PER_MINUTE:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "注册过于频繁，请稍后再试")


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """注册：仅开放普通用户。

    安全要点：
    - role 由服务端固定为 user，入参 schema 里根本没有该字段，
      客户端偷传 "role": "admin" 会被直接忽略（防自我提权）；
    - 注册成功直接签发双令牌，前端无需再登录一次；
    - 按来源 IP 限流，防止脚本批量注册。
    """
    _check_register_rate(request.client.host if request.client else "unknown")
    exists = db.scalar(select(User).where(User.username == body.username))
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "用户名已被占用")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.username,
        role=UserRole.user,  # 只能注册普通用户：角色在服务端写死
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenPair(
        access_token=create_token(user.id, user.role.value, "access"),
        refresh_token=create_token(user.id, user.role.value, "refresh"),
    )


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
    try:
        # 损坏的令牌 sub 可能不是合法 UUID：按无效处理（401），不抛 500
        user_id = uuid.UUID(str(payload.get("sub", "")))
    except (ValueError, AttributeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token 无效")
    user = db.get(User, user_id)
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
