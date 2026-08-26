import uuid

from app.models.eval import EvalDataset, EvalRun
from app.models.kb import Chunk, Document, KnowledgeBase
from app.models.task import TaskKind, TaskStatus
from tests.conftest import auth_headers, login, make_user


def _seed(db, user):
    kb = KnowledgeBase(name="kb", owner_id=user.id, visibility="private")
    db.add(kb)
    db.flush()
    doc = Document(kb_id=kb.id, filename="公司介绍.txt", filetype="txt", created_by=user.id)
    db.add(doc)
    db.flush()
    from tests.test_retrieval import rand_vector

    vec = rand_vector(11)
    db.add(Chunk(kb_id=kb.id, document_id=doc.id, content="拾光茶屋成立于2020年，总部在杭州。",
                 token_count=10, meta={}, embedding=vec))
    db.commit()
    return kb, vec


def test_dataset_crud(client, db):
    make_user(db, "alice")
    h = auth_headers(login(client, "alice")["access_token"])

    resp = client.post(
        "/api/eval/datasets",
        json={"name": "冒烟集", "items": [{"question": "公司哪年成立？", "expect_keywords": ["2020"]}]},
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    ds_id = resp.json()["id"]

    resp = client.get("/api/eval/datasets", headers=h)
    assert len(resp.json()) == 1

    # 缺少 question 的评测项被拒绝
    resp = client.post("/api/eval/datasets", json={"name": "bad", "items": [{"expect_keywords": []}]}, headers=h)
    assert resp.status_code == 400

    assert client.delete(f"/api/eval/datasets/{ds_id}", headers=h).status_code == 204


def test_run_requires_dataset_and_kb_access(client, db):
    make_user(db, "alice")
    h = auth_headers(login(client, "alice")["access_token"])

    fake_ds = uuid.uuid4()
    kb_id = uuid.uuid4()
    resp = client.post(
        "/api/eval/runs", json={"dataset_id": str(fake_ds), "kb_ids": [str(kb_id)]}, headers=h
    )
    assert resp.status_code == 404


def test_run_enqueues_task(client, db):
    from sqlalchemy import select
    from app.models.task import Task

    user = make_user(db, "alice")
    kb, _ = _seed(db, user)
    h = auth_headers(login(client, "alice")["access_token"])

    ds = client.post(
        "/api/eval/datasets",
        json={"name": "d", "items": [{"question": "q", "expect_doc": "公司介绍"}]},
        headers=h,
    ).json()

    resp = client.post(
        "/api/eval/runs", json={"dataset_id": ds["id"], "kb_ids": [str(kb.id)]}, headers=h
    )
    assert resp.status_code == 201, resp.text
    run = resp.json()
    assert run["status"] == "queued"

    tasks = db.scalars(select(Task)).all()
    assert any(t.kind == TaskKind.eval_run and t.payload == {"eval_run_id": run["id"]} for t in tasks)


def test_execute_eval_run_end_to_end(db, monkeypatch):
    """worker 执行路径：mock 掉模型调用，端到端跑通评测并校验指标。"""
    import app.services.eval as eval_mod
    from app.config import settings
    from tests.test_retrieval import rand_vector

    monkeypatch.setattr(settings, "rerank_enabled", False)
    user = make_user(db, "alice")
    kb, vec = _seed(db, user)

    ds = EvalDataset(
        name="d",
        items=[
            {"question": "公司哪年成立？", "expect_keywords": ["2020"], "expect_doc": "公司介绍"},
            {"question": "空问题", "expect_doc": ""},
        ],
        created_by=user.id,
    )
    db.add(ds)
    db.flush()
    run = EvalRun(dataset_id=ds.id, config={"kb_ids": [str(kb.id)]}, created_by=user.id)
    db.add(run)
    db.commit()

    monkeypatch.setattr(eval_mod, "embed_texts", lambda texts: [vec])
    monkeypatch.setattr(eval_mod, "stream_chat", lambda messages: iter(["成立于2020年。"]))
    monkeypatch.setattr(
        eval_mod, "judge_answer", lambda q, m, a: {"faithfulness": 5, "relevance": 4}
    )

    eval_mod.execute_eval_run(db, run.id)

    db.refresh(run)
    assert run.status == TaskStatus.done
    m = run.metrics
    assert m["total"] == 2
    assert m["retrieval_hit"] == 1  # 只有第一题设置了 expect_doc
    assert m["retrieval_precision"] == 1.0
    assert m["avg_keyword_rate"] == 1.0
    assert m["avg_faithfulness"] == 5
    assert len(run.results) == 2
    first = run.results[0]
    assert first["retrieval_hit"] is True
    assert "2020" in first["keyword_hits"]
