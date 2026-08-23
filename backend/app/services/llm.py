"""LLM chat helpers: prompt building, history trimming, streaming."""
from collections.abc import Iterator

from app.models.chat import Message, MessageRole
from app.services.embedding import get_client
from app.config import settings

SYSTEM_PROMPT = """你是一个企业知识库问答助手。请只根据下方【参考资料】回答用户问题。

要求：
1. 引用资料时使用 [编号] 标注出处，例如 [1]、[2]；
2. 资料不足以回答时，明确告知用户，不要编造；
3. 回答简洁、准确，使用中文。"""

HISTORY_CHAR_BUDGET = 4000


def trim_history(messages: list[Message], char_budget: int = HISTORY_CHAR_BUDGET) -> list[dict]:
    """Keep the most recent turns that fit into the char budget."""
    picked: list[dict] = []
    total = 0
    for m in reversed(messages):
        content = m.content or ""
        if total + len(content) > char_budget:
            break
        picked.append({"role": m.role.value, "content": content})
        total += len(content)
    return list(reversed(picked))


def build_chat_messages(
    history: list[dict],
    question: str,
    materials: list[tuple[int, str, str]],
) -> list[dict]:
    """materials: list of (index, content, source_label)."""
    if materials:
        refs = "\n\n".join(f"[{i}] ({label})\n{content}" for i, content, label in materials)
    else:
        refs = "（无）"
    system = SYSTEM_PROMPT + "\n\n【参考资料】\n" + refs
    return [{"role": "system", "content": system}] + history + [{"role": "user", "content": question}]


def stream_chat(messages: list[dict]) -> Iterator[str]:
    """Yield answer tokens from the LLM."""
    client = get_client()
    stream = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        stream=True,
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is not None and delta.content:
            yield delta.content


def last_messages(db, conversation_id, limit: int = 20) -> list[Message]:
    from sqlalchemy import select

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, Message.id)
    )
    msgs = list(db.scalars(stmt).all())
    return msgs[-limit:]
