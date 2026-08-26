# FastAPI 依赖注入：当前用户、管理员校验、知识库权限判断。
# 这是整个系统权限体系的核心，所有受保护接口都从这里取用户和权限。
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
    """从请求头 Bearer 令牌解析当前用户。失败一律 401。"""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录或凭证缺失")
    try:
        payload = decode_token(credentials.credentials, token_type="access")
    except pyjwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"凭证无效或已过期: {e}")
    user = db.get(User, uuid.UUID(payload["sub"]))
    # 令牌有效但用户已被删除/停用，同样拒绝
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已停用")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """仅管理员可访问的接口用这个依赖，否则 403。"""
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user


def visible_kb_ids_query(user: User):
    """返回"当前用户可见的所有知识库 ID"的 SQLAlchemy 查询。

    可见性规则 = 自己创建的 ∪ 作为成员加入的 ∪ 公开的，三者取并集。
    知识库列表接口用它做行级过滤。
    """
    own = select(KnowledgeBase.id).where(KnowledgeBase.owner_id == user.id)
    member = select(KbMember.kb_id).where(KbMember.user_id == user.id)
    public = select(KnowledgeBase.id).where(KnowledgeBase.visibility == "public")
    return union(own, member, public)


def get_accessible_kb(kb_id: uuid.UUID, user: User, db: Session) -> KnowledgeBase:
    """按 ID 取知识库并做访问校验。无权访问抛 403，不存在抛 404。

    放行条件（满足其一）：管理员 / 创建者 / 公开库 / 库成员。
    """
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
    """判断用户能否管理该库的文档与成员：创建者 / 管理员 / editor 成员。
    （viewer 成员只能读，不能写。）"""
    if user.role == UserRole.admin or kb.owner_id == user.id:
        return True
    member = db.scalar(select(KbMember).where(KbMember.kb_id == kb.id, KbMember.user_id == user.id))
    return member is not None and member.role.value == "editor"
