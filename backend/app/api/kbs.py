# 知识库接口：CRUD + 成员管理。
# 所有接口都先过权限校验（见 core/deps.py）：
#   读操作 —— 可见即可读（创建者/成员/公开/管理员）
#   写操作 —— 仅创建者或管理员
#   成员管理 —— 创建者/管理员/editor 成员
import shutil
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import (
    can_edit_kb,
    get_accessible_kb,
    get_current_user,
    visible_kb_ids_query,
)
from app.db import get_db
from app.models.kb import Chunk, Document, KbMember, KnowledgeBase
from app.models.user import User, UserRole
from app.schemas.kb import KbCreate, KbOut, KbUpdate, MemberCreate, MemberOut

router = APIRouter(prefix="/api/kbs", tags=["kbs"])


def _kb_counts(db: Session, kb_ids: list[uuid.UUID]) -> tuple[dict, dict]:
    """批量统计文档数与切片数（两条 GROUP BY 查询，替代逐库 count 的 N+1）。"""
    if not kb_ids:
        return {}, {}
    doc_counts = dict(
        db.execute(
            select(Document.kb_id, func.count(Document.id))
            .where(Document.kb_id.in_(kb_ids))
            .group_by(Document.kb_id)
        ).all()
    )
    chunk_counts = dict(
        db.execute(
            select(Chunk.kb_id, func.count(Chunk.id))
            .where(Chunk.kb_id.in_(kb_ids))
            .group_by(Chunk.kb_id)
        ).all()
    )
    return doc_counts, chunk_counts


def _to_out(kb: KnowledgeBase, db: Session) -> KbOut:
    """组装知识库出参：附加实时的文档数与切片数统计（单库场景用）。"""
    doc_count = db.scalar(select(func.count(Document.id)).where(Document.kb_id == kb.id)) or 0
    chunk_count = db.scalar(select(func.count(Chunk.id)).where(Chunk.kb_id == kb.id)) or 0
    out = KbOut.model_validate(kb)
    out.doc_count = doc_count
    out.chunk_count = chunk_count
    return out


@router.get("", response_model=list[KbOut])
def list_kbs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """列出当前用户可见的知识库（自己创建的 ∪ 作为成员的 ∪ 公开的）。"""
    stmt = select(KnowledgeBase).where(KnowledgeBase.id.in_(visible_kb_ids_query(user))).order_by(
        KnowledgeBase.created_at.desc()
    )
    kbs = list(db.scalars(stmt).all())
    # 列表场景批量聚合统计，避免"每个库两次 count"的 N+1 查询
    doc_counts, chunk_counts = _kb_counts(db, [kb.id for kb in kbs])
    outs: list[KbOut] = []
    for kb in kbs:
        out = KbOut.model_validate(kb)
        out.doc_count = doc_counts.get(kb.id, 0)
        out.chunk_count = chunk_counts.get(kb.id, 0)
        outs.append(out)
    return outs


@router.post("", response_model=KbOut, status_code=status.HTTP_201_CREATED)
def create_kb(body: KbCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kb = KnowledgeBase(
        name=body.name,
        description=body.description,
        visibility=body.visibility,
        owner_id=user.id,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return _to_out(kb, db)


@router.get("/{kb_id}", response_model=KbOut)
def get_kb(kb_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kb = get_accessible_kb(kb_id, user, db)
    return _to_out(kb, db)


@router.patch("/{kb_id}", response_model=KbOut)
def update_kb(
    kb_id: uuid.UUID,
    body: KbUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = get_accessible_kb(kb_id, user, db)
    if user.role != UserRole.admin and kb.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "只有创建者或管理员可以修改知识库")
    if body.name is not None:
        kb.name = body.name
    if body.description is not None:
        kb.description = body.description
    if body.visibility is not None:
        kb.visibility = body.visibility
    db.commit()
    db.refresh(kb)
    return _to_out(kb, db)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kb(
    kb_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = get_accessible_kb(kb_id, user, db)
    if user.role != UserRole.admin and kb.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "只有创建者或管理员可以删除知识库")
    db.delete(kb)
    db.commit()
    # 清理磁盘：删除该库的上传目录（数据库行已级联删除，
    # 但原始文件在 uploads/{kb_id}/ 下，不清理会长期残留）
    shutil.rmtree(settings.upload_path / str(kb_id), ignore_errors=True)


@router.get("/{kb_id}/members", response_model=list[MemberOut])
def list_members(
    kb_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = get_accessible_kb(kb_id, user, db)
    rows = db.execute(
        select(KbMember, User).join(User, KbMember.user_id == User.id).where(KbMember.kb_id == kb.id)
    ).all()
    return [
        MemberOut(user_id=m.user_id, username=u.username, display_name=u.display_name, role=m.role)
        for m, u in rows
    ]


@router.post("/{kb_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    kb_id: uuid.UUID,
    body: MemberCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = get_accessible_kb(kb_id, user, db)
    if not can_edit_kb(kb, user, db):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权管理该知识库成员")
    target = db.get(User, body.user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    existing = db.get(KbMember, (kb_id, body.user_id))
    if existing is not None:
        existing.role = body.role  # 已是成员则更新角色（幂等）
    else:
        db.add(KbMember(kb_id=kb_id, user_id=body.user_id, role=body.role))
    db.commit()
    return MemberOut(
        user_id=target.id, username=target.username, display_name=target.display_name, role=body.role
    )


@router.delete("/{kb_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = get_accessible_kb(kb_id, user, db)
    if not can_edit_kb(kb, user, db):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权管理该知识库成员")
    member = db.get(KbMember, (kb_id, user_id))
    if member is not None:
        db.delete(member)
        db.commit()
