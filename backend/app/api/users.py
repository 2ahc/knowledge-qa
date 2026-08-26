# 用户管理接口：
#   /search  —— 任何登录用户可用（给共享知识库挑成员用），只返回启用账号
#   其余接口 —— 仅管理员（用户列表/创建/修改）
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.security import hash_password
from app.db import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/search", response_model=list[UserOut])
def search_users(
    q: str = "",
    limit: int = 20,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按用户名/显示名模糊搜索用户（供知识库添加成员时选人）。"""
    stmt = select(User).where(User.is_active.is_(True))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(User.username.ilike(like) | User.display_name.ilike(like))
    return db.scalars(stmt.order_by(User.username).limit(min(max(limit, 1), 50))).all()


@router.get("", response_model=list[UserOut])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.created_at)).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.username == body.username))
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "用户名已存在")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.username,
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.role is not None:
        # 自我保护：管理员不能取消自己的管理员权限（防止系统失去管理员）
        if user.id == admin.id and body.role.value != "admin":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能取消自己的管理员权限")
        user.role = body.role
    if body.is_active is not None:
        # 自我保护：不能停用自己的账号
        if user.id == admin.id and not body.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能停用自己的账号")
        user.is_active = body.is_active
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(user)
    return user
