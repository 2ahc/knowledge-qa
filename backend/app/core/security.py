import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(user_id: uuid.UUID, role: str, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    if token_type == "refresh":
        exp = now + timedelta(days=settings.refresh_token_days)
    else:
        exp = now + timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, token_type: str = "access") -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on any problem."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != token_type:
        raise jwt.InvalidTokenError(f"expected {token_type} token")
    return payload
