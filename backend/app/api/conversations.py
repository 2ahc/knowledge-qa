# 会话接口：历史会话列表 / 创建 / 改名 / 删除 / 查看消息。
# 会话严格归属个人（只能操作自己的会话）。
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.chat import Conversation, Message
from app.models.user import User
from app.schemas.chat import ConversationCreate, ConversationOut, ConversationUpdate, MessageOut

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _to_out(conv: Conversation, db: Session) -> ConversationOut:
    """组装会话出参：附加消息条数（侧边栏展示用）。"""
    count = db.scalar(
        select(func.count(Message.id)).where(Message.conversation_id == conv.id)
    ) or 0
    out = ConversationOut.model_validate(conv)
    out.message_count = count
    return out


def _get_own(conv_id: uuid.UUID, user: User, db: Session) -> Conversation:
    """取当前用户自己的会话；不是自己的或不存在一律 404（不泄露存在性）。"""
    conv = db.get(Conversation, conv_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    return conv


@router.get("", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.created_at.desc())
    convs = list(db.scalars(stmt).all())
    # 批量聚合消息数（一条 GROUP BY），避免"每个会话一次 count"的 N+1
    counts = dict(
        db.execute(
            select(Message.conversation_id, func.count(Message.id))
            .where(Message.conversation_id.in_([c.id for c in convs]))
            .group_by(Message.conversation_id)
        ).all()
    ) if convs else {}
    outs: list[ConversationOut] = []
    for c in convs:
        out = ConversationOut.model_validate(c)
        out.message_count = counts.get(c.id, 0)
        outs.append(out)
    return outs


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = Conversation(user_id=user.id, title=body.title, kb_ids=[str(k) for k in body.kb_ids])
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _to_out(conv, db)


@router.patch("/{conv_id}", response_model=ConversationOut)
def update_conversation(
    conv_id: uuid.UUID,
    body: ConversationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = _get_own(conv_id, user, db)
    if body.title is not None:
        conv.title = body.title
    if body.kb_ids is not None:
        conv.kb_ids = [str(k) for k in body.kb_ids]
    db.commit()
    db.refresh(conv)
    return _to_out(conv, db)


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = _get_own(conv_id, user, db)
    db.delete(conv)
    db.commit()


@router.get("/{conv_id}/messages", response_model=list[MessageOut])
def list_messages(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = _get_own(conv_id, user, db)
    stmt = select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at, Message.id)
    return db.scalars(stmt).all()
