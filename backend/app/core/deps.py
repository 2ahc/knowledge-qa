import uuid

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select, union
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db import get_db
from app.models.kb import KbMember, KnowledgeBase
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录或凭证缺失")
    try:
        payload = decode_token(credentials.credentials, token_type="access")
    except pyjwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"凭证无效或已过期: {e}")
    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已停用")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user


def visible_kb_ids_query(user: User):
    """SQLAlchemy select returning kb ids visible to the user."""
    own = select(KnowledgeBase.id).where(KnowledgeBase.owner_id == user.id)
    member = select(KbMember.kb_id).where(KbMember.user_id == user.id)
    public = select(KnowledgeBase.id).where(KnowledgeBase.visibility == "public")
    return union(own, member, public)


def get_accessible_kb(kb_id: uuid.UUID, user: User, db: Session) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识库不存在")
    if user.role == UserRole.admin or kb.owner_id == user.id or kb.visibility == "public":
        return kb
    is_member = db.scalar(select(KbMember).where(KbMember.kb_id == kb_id, KbMember.user_id == user.id))
    if is_member is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该知识库")
    return kb


def can_edit_kb(kb: KnowledgeBase, user: User, db: Session) -> bool:
    """owner / admin / editor member can manage docs & members."""
    if user.role == UserRole.admin or kb.owner_id == user.id:
        return True
    member = db.scalar(select(KbMember).where(KbMember.kb_id == kb.id, KbMember.user_id == user.id))
    return member is not None and member.role.value == "editor"
