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
    count = db.scalar(
        select(func.count(Message.id)).where(Message.conversation_id == conv.id)
    ) or 0
    out = ConversationOut.model_validate(conv)
    out.message_count = count
    return out


def _get_own(conv_id: uuid.UUID, user: User, db: Session) -> Conversation:
    conv = db.get(Conversation, conv_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    return conv


@router.get("", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.created_at.desc())
    return [_to_out(c, db) for c in db.scalars(stmt).all()]


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
