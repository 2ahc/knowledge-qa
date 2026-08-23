import random
import uuid

import pytest

from app.models.kb import Chunk, Document, KnowledgeBase
from app.services.retrieval import hybrid_retrieve, location_label, rrf_merge


def make_kb_and_doc(db, user):
    kb = KnowledgeBase(name="kb", owner_id=user.id, visibility="private")
    db.add(kb)
    db.flush()
    doc = Document(kb_id=kb.id, filename="产品手册.pdf", filetype="pdf", created_by=user.id)
    db.add(doc)
    db.flush()
    return kb, doc


def rand_vector(seed: int, dim: int = 1024) -> list[float]:
    rnd = random.Random(seed)
    return [rnd.uniform(-1, 1) for _ in range(dim)]


def test_rrf_merge_ranks():
    a = [uuid.uuid4(), uuid.uuid4()]
    b = [a[1], uuid.uuid4()]
    scores = rrf_merge([a, b], k=60)
    # a[1] appears in both lists -> highest score
    assert scores[a[1]] > scores[a[0]]


def test_location_label():
    assert "第 3 页" in location_label({"page": 3})
    assert "工作表" in location_label({"sheet": "员工表"})
    assert location_label({}) == ""


def test_hybrid_retrieve_returns_matching_chunk(db, monkeypatch):
    from app.config import settings
    from tests.conftest import make_user

    monkeypatch.setattr(settings, "rerank_enabled", False)
    user = make_user(db, "alice")
    kb, doc = make_kb_and_doc(db, user)

    target = rand_vector(1)
    other = rand_vector(2)
    db.add(Chunk(kb_id=kb.id, document_id=doc.id, content="公司成立于2020年，总部在杭州。",
                 token_count=10, meta={"page": 1}, embedding=target))
    db.add(Chunk(kb_id=kb.id, document_id=doc.id, content="员工福利包括五险一金和带薪年假。",
                 token_count=10, meta={"page": 2}, embedding=other))
    db.commit()

    # query vector == target -> first chunk should rank first
    results = hybrid_retrieve(db, [kb.id], "公司成立于哪一年", target, top_k=2)
    assert len(results) >= 1
    assert "成立于2020" in results[0].content
    assert results[0].filename == "产品手册.pdf"


def test_hybrid_retrieve_respects_kb_scope(db, monkeypatch):
    from app.config import settings
    from tests.conftest import make_user

    monkeypatch.setattr(settings, "rerank_enabled", False)
    user = make_user(db, "alice")
    kb1, doc1 = make_kb_and_doc(db, user)
    kb2 = KnowledgeBase(name="kb2", owner_id=user.id, visibility="private")
    db.add(kb2)
    db.flush()
    doc2 = Document(kb_id=kb2.id, filename="其他库.docx", filetype="docx", created_by=user.id)
    db.add(doc2)
    db.flush()

    vec = rand_vector(7)
    db.add(Chunk(kb_id=kb2.id, document_id=doc2.id, content="只属于另一个库的内容。",
                 token_count=5, meta={}, embedding=vec))
    db.commit()

    # searching kb1 only must not leak kb2 chunks
    results = hybrid_retrieve(db, [kb1.id], "另一个库的内容", vec, top_k=5)
    assert all(r.filename != "其他库.docx" for r in results)
