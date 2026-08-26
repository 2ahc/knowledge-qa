# LLM 问答辅助：提示词构建、历史裁剪、流式生成、LLM 裁判评分。
from collections.abc import Iterator

from app.models.chat import Message, MessageRole
from app.services.embedding import get_client
from app.config import settings

# 系统提示词：约束模型只基于检索到的资料回答。
# 三条铁律 —— 引用标注出处、资料不足不编造、中文简洁回答。
# 修改回答风格（语气/格式/语言）就在这里改。
SYSTEM_PROMPT = """你是一个企业知识库问答助手。请只根据下方【参考资料】回答用户问题。

要求：
1. 引用资料时使用 [编号] 标注出处，例如 [1]、[2]；
2. 资料不足以回答时，明确告知用户，不要编造；
3. 回答简洁、准确，使用中文。"""

# 多轮历史的字符预算：超出部分从最旧的开始丢弃，控制上下文长度与成本
HISTORY_CHAR_BUDGET = 4000


def trim_history(messages: list[Message], char_budget: int = HISTORY_CHAR_BUDGET) -> list[dict]:
    """裁剪多轮历史：从最新消息往回取，直到累计字符数超出预算为止。

    为什么不用条数裁剪：一条消息可能很长（比如粘贴了大段文本），
    按字符预算控制才能真正限制 token 消耗。
    """
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
    """组装发给大模型的完整消息列表：
    [系统提示词+参考资料] + [历史对话] + [当前问题]

    materials: [(编号, 切片内容, 出处标签), ...]，编号与回答里的 [n] 对应。
    把资料放在 system 里而非 user 里，可降低模型把资料当问题的概率。
    """
    if materials:
        refs = "\n\n".join(f"[{i}] ({label})\n{content}" for i, content, label in materials)
    else:
        refs = "（无）"
    system = SYSTEM_PROMPT + "\n\n【参考资料】\n" + refs
    return [{"role": "system", "content": system}] + history + [{"role": "user", "content": question}]


def stream_chat(messages: list[dict]) -> Iterator[str]:
    """调用大模型流式生成，逐块产出回答文本（供 SSE 逐字推送给前端）。"""
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
    """取会话最近 limit 条消息（按时间正序返回），供构建多轮上下文。"""
    from sqlalchemy import select

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, Message.id)
    )
    msgs = list(db.scalars(stmt).all())
    return msgs[-limit:]


# 评测用裁判提示词：让 LLM 给"回答"打分（LLM-as-judge 方法）。
# 两个维度：忠实性（是否忠于资料、不编造）与相关性（是否切题）。
JUDGE_PROMPT = """你是一个问答质量评审员。请根据【参考资料】【问题】【回答】，从两个维度打分（1-5 的整数）：
- faithfulness（忠实性）：回答是否完全基于资料，无编造内容
- relevance（相关性）：回答是否切题、解决了问题

只输出 JSON，例如：{"faithfulness": 4, "relevance": 5}"""


def judge_answer(question: str, materials_text: str, answer: str) -> dict:
    """LLM 裁判打分，返回 {faithfulness, relevance}；解析失败记 0 分。"""
    import json as _json
    import re

    client = get_client()
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": JUDGE_PROMPT},
            {
                "role": "user",
                "content": f"【参考资料】\n{materials_text}\n\n【问题】\n{question}\n\n【回答】\n{answer}",
            },
        ],
    )
    text = resp.choices[0].message.content or ""
    # 裁判输出可能带多余文字，用正则抠出 JSON 部分
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            data = _json.loads(m.group(0))
            return {
                "faithfulness": int(data.get("faithfulness", 0)),
                "relevance": int(data.get("relevance", 0)),
            }
        except (ValueError, TypeError):
            pass
    return {"faithfulness": 0, "relevance": 0}
