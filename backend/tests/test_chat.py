import json

from app.models.kb import Chunk, Document, KnowledgeBase
from tests.conftest import auth_headers, login, make_user


def parse_sse(text: str) -> list[dict]:
    """把 SSE 响应文本解析成事件字典列表（测试用）。"""
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def _seed_kb_with_chunk(db, user, content="拾光茶屋成立于2020年，总部位于杭州。"):
    kb = KnowledgeBase(name="kb", owner_id=user.id, visibility="private")
    db.add(kb)
    db.flush()
    doc = Document(kb_id=kb.id, filename="公司介绍.txt", filetype="txt", created_by=user.id)
    db.add(doc)
    db.flush()
    from tests.test_retrieval import rand_vector

    db.add(Chunk(kb_id=kb.id, document_id=doc.id, content=content, token_count=10,
                 meta={"page": 1}, embedding=rand_vector(3)))
    db.commit()
    return kb


def test_chat_streams_and_persists(client, db, monkeypatch):
    import app.api.chat as chat_mod
    import app.services.retrieval as ret_mod
    from app.config import settings
    from tests.test_retrieval import rand_vector

    monkeypatch.setattr(settings, "rerank_enabled", False)
    qvec = rand_vector(3)  # 与预置切片的向量相同 → 保证必然检索命中
    monkeypatch.setattr(chat_mod, "embed_texts", lambda texts: [qvec])
    monkeypatch.setattr(ret_mod, "rerank", lambda q, docs, n: [(i, 0.9) for i in range(min(n, len(docs)))])
    monkeypatch.setattr(chat_mod, "stream_chat", lambda messages: ["公司", "成立于2020年。"])

    user = make_user(db, "alice")
    kb = _seed_kb_with_chunk(db, user)
    h = auth_headers(login(client, "alice")["access_token"])

    resp = client.post(
        "/api/chat",
        json={"question": "公司成立于哪一年？", "kb_ids": [str(kb.id)]},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    events = parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert "citations" in types
    assert "token" in types
    assert "done" in types

    # 引用事件携带文件名（与出处内容）
    cit = next(e for e in events if e["type"] == "citations")
    assert cit["citations"][0]["filename"] == "公司介绍.txt"

    # 回答 = 所有 token 事件内容的拼接
    answer = "".join(e["content"] for e in events if e["type"] == "token")
    assert answer == "公司成立于2020年。"

    # 会话与消息已持久化（用户消息 + AI 回答）
    convs = client.get("/api/conversations", headers=h).json()
    assert len(convs) == 1
    assert convs[0]["message_count"] == 2
    msgs = client.get(f"/api/conversations/{convs[0]['id']}/messages", headers=h).json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["content"] == "公司成立于2020年。"
    assert msgs[1]["citations"][0]["filename"] == "公司介绍.txt"


def test_chat_empty_retrieval_no_generation(client, db, monkeypatch):
    """检索为空时：走兜底话术，绝不调用大模型（防编造 + 省成本）。"""
    import app.api.chat as chat_mod
    from app.config import settings

    monkeypatch.setattr(settings, "rerank_enabled", False)
    called = {"stream": False}

    def fake_stream(messages):
        called["stream"] = True
        yield "不应生成"

    monkeypatch.setattr(chat_mod, "embed_texts", lambda texts: [[0.0] * 1024])
    monkeypatch.setattr(chat_mod, "stream_chat", fake_stream)

    user = make_user(db, "bob")
    kb = KnowledgeBase(name="empty-kb", owner_id=user.id, visibility="private")
    db.add(kb)
    db.commit()
    h = auth_headers(login(client, "bob")["access_token"])

    resp = client.post(
        "/api/chat", json={"question": "随便问点什么", "kb_ids": [str(kb.id)]}, headers=h
    )
    assert resp.status_code == 200
    events = parse_sse(resp.text)
    assert not called["stream"], "检索为空时不允许调用大模型"
    answer = "".join(e["content"] for e in events if e["type"] == "token")
    assert "未在所选知识库中检索到" in answer


def test_chat_requires_kb_access(client, db):
    user = make_user(db, "alice")
    make_user(db, "eve")
    kb = KnowledgeBase(name="private-kb", owner_id=user.id, visibility="private")
    db.add(kb)
    db.commit()
    h = auth_headers(login(client, "eve")["access_token"])
    resp = client.post(
        "/api/chat", json={"question": "hi", "kb_ids": [str(kb.id)]}, headers=h
    )
    assert resp.status_code == 403
