# 安全基础：密码哈希 + JWT 签发/校验。
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str) -> str:
    """bcrypt 加盐哈希，数据库只存哈希，永远不存明文密码。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配；哈希格式非法时按校验失败处理。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(user_id: uuid.UUID, role: str, token_type: str) -> str:
    """签发 JWT。

    token_type:
      - access：短期（默认 2 小时），携带在每个请求头里
      - refresh：长期（默认 7 天），仅用于换取新的 access 令牌
    """
    now = datetime.now(timezone.utc)
    if token_type == "refresh":
        exp = now + timedelta(days=settings.refresh_token_days)
    else:
        exp = now + timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user_id),  # 用户 ID
        "role": role,  # 角色（admin/user），服务端仍以数据库为准做二次校验
        "type": token_type,  # 令牌类型，防止拿 refresh 令牌冒充 access
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, token_type: str = "access") -> dict:
    """解码并校验 JWT。任何异常（签名错误/过期/类型不符）都抛 jwt.PyJWTError。"""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != token_type:
        raise jwt.InvalidTokenError(f"expected {token_type} token")
    return payload
