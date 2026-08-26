"""SSE 流式问答接口：检索 → 生成 → 持久化。

整个问答主链路都在这里。事件流协议（前端 sse.ts 解析）：
  {"type": "token", "content": "..."}        回答的增量文本（逐块推送）
  {"type": "citations", "citations": [...]}  本次回答的引用来源列表
  {"type": "done", "conversation_id", ...}   结束事件，携带会话与消息 ID
  {"type": "error", "message": "..."}        过程中出错
"""
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

# 检索为空时的兜底回答：如实告知，不调用大模型（省成本 + 杜绝编造）
EMPTY_RESULT_ANSWER = "抱歉，未在所选知识库中检索到与问题相关的内容。请确认文档已索引完成，或尝试更换问法。"


def _sse(data: dict) -> str:
    """把事件字典包装成 SSE 数据帧（data: {...}\\n\\n）。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
def chat(body: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not settings.dashscope_api_key:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "DASHSCOPE_API_KEY 未配置")

    # 逐个校验知识库访问权限（无权直接 403）
    for kb_id in body.kb_ids:
        get_accessible_kb(kb_id, user, db)

    # 取或建会话：新会话以首条提问的前 50 字作为标题
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
        """SSE 生成器：流式响应在独立线程执行，不能用请求级 Session
        （请求结束就关闭了），所以这里新建一个专用 Session。"""
        sdb: Session = db_module.SessionLocal()
        try:
            started = time.time()

            # 1) 多轮历史：取本条提问之前的消息，按字符预算裁剪
            history = trim_history(last_messages(sdb, conversation_id))

            # 2) 持久化用户提问
            sdb.add(Message(conversation_id=conversation_id, role=MessageRole.user, content=question))
            sdb.commit()

            # 3) 混合检索：先向量化问题，再走 向量+关键词→融合→重排 链路
            try:
                query_vector = embed_texts([question])[0]
            except Exception as e:  # noqa: BLE001
                yield _sse({"type": "error", "message": f"查询向量化失败: {e}"})
                return
            chunks = hybrid_retrieve(sdb, kb_ids, question, query_vector)

            # 组装引用信息（前端引用卡片 + 回答里的 [n] 编号对应）
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

            # 4) 检索为空：如实兜底，不调用大模型（避免编造 + 省成本）
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

            # 5) 先推引用事件，前端可立即渲染引用卡片，无需等回答生成完
            yield _sse({"type": "citations", "citations": citations})

            # 6) 组装提示词：[系统提示+资料] + [多轮历史] + [当前问题]
            materials = [
                (i + 1, c.content, f"{c.filename} {location_label(c.meta)}".strip())
                for i, c in enumerate(chunks)
            ]
            messages = build_chat_messages(history, question, materials)

            # 7) 流式生成：每个 token 立即推给前端（打字机效果）
            answer_parts: list[str] = []
            try:
                for token in stream_chat(messages):
                    answer_parts.append(token)
                    yield _sse({"type": "token", "content": token})
            except Exception as e:  # noqa: BLE001
                yield _sse({"type": "error", "message": f"生成回答失败: {e}"})

            # 8) 持久化完整回答（含引用与耗时），供历史会话回看
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
        # 禁用缓存与代理缓冲：SSE 必须实时透传，缓冲会导致"打字机"变"一次性蹦出"
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
