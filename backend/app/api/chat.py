"""Streaming Q&A endpoint: retrieve -> generate (SSE) -> persist."""
import json
import time
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_accessible_kb, get_current_user
from app import db as db_module
from app.db import get_db
from app.models.chat import Conversation, Message, MessageRole
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.services.embedding import embed_texts
from app.services.llm import build_chat_messages, last_messages, stream_chat, trim_history
from app.services.retrieval import hybrid_retrieve, location_label

router = APIRouter(prefix="/api", tags=["chat"])

EMPTY_RESULT_ANSWER = "抱歉，未在所选知识库中检索到与问题相关的内容。请确认文档已索引完成，或尝试更换问法。"


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
def chat(body: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not settings.dashscope_api_key:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "DASHSCOPE_API_KEY 未配置")

    for kb_id in body.kb_ids:
        get_accessible_kb(kb_id, user, db)

    if body.conversation_id is not None:
        conv = db.get(Conversation, body.conversation_id)
        if conv is None or conv.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
        if body.question and (not conv.title):
            conv.title = body.question[:50]
    else:
        conv = Conversation(
            user_id=user.id,
            title=body.question[:50],
            kb_ids=[str(k) for k in body.kb_ids],
        )
        db.add(conv)
    db.commit()
    db.refresh(conv)

    conversation_id = conv.id
    question = body.question
    kb_ids = list(body.kb_ids)

    def generate() -> Iterator[str]:
        sdb: Session = db_module.SessionLocal()
        try:
            started = time.time()

            # history (before this question)
            history = trim_history(last_messages(sdb, conversation_id))

            # persist the user message
            sdb.add(Message(conversation_id=conversation_id, role=MessageRole.user, content=question))
            sdb.commit()

            # retrieval
            try:
                query_vector = embed_texts([question])[0]
            except Exception as e:  # noqa: BLE001
                yield _sse({"type": "error", "message": f"查询向量化失败: {e}"})
                return
            chunks = hybrid_retrieve(sdb, kb_ids, question, query_vector)

            citations = [
                {
                    "chunk_id": str(c.chunk_id),
                    "document_id": str(c.document_id),
                    "filename": c.filename,
                    "location": location_label(c.meta),
                    "content": c.content,
                    "score": c.score,
                }
                for c in chunks
            ]

            # no retrieval hits: honest fallback, no generation
            if not chunks:
                answer = EMPTY_RESULT_ANSWER
                yield _sse({"type": "token", "content": answer})
                yield _sse({"type": "citations", "citations": []})
                am = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.assistant,
                    content=answer,
                    citations=[],
                    latency_ms=int((time.time() - started) * 1000),
                )
                sdb.add(am)
                sdb.commit()
                yield _sse({"type": "done", "conversation_id": str(conversation_id), "message_id": str(am.id)})
                return

            yield _sse({"type": "citations", "citations": citations})

            materials = [
                (i + 1, c.content, f"{c.filename} {location_label(c.meta)}".strip())
                for i, c in enumerate(chunks)
            ]
            messages = build_chat_messages(history, question, materials)

            answer_parts: list[str] = []
            try:
                for token in stream_chat(messages):
                    answer_parts.append(token)
                    yield _sse({"type": "token", "content": token})
            except Exception as e:  # noqa: BLE001
                yield _sse({"type": "error", "message": f"生成回答失败: {e}"})

            am = Message(
                conversation_id=conversation_id,
                role=MessageRole.assistant,
                content="".join(answer_parts),
                citations=citations,
                latency_ms=int((time.time() - started) * 1000),
            )
            sdb.add(am)
            sdb.commit()
            yield _sse({"type": "done", "conversation_id": str(conversation_id), "message_id": str(am.id)})
        finally:
            sdb.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
