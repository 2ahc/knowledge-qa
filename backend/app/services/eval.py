"""Evaluation executor: retrieval hit-rate + keyword coverage + LLM judge."""
import logging
import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.models.eval import EvalDataset, EvalRun
from app.models.task import TaskStatus
from app.services.embedding import embed_texts
from app.services.llm import build_chat_messages, judge_answer, stream_chat
from app.services.retrieval import hybrid_retrieve, location_label

logger = logging.getLogger(__name__)


def execute_eval_run(db: Session, eval_run_id: uuid.UUID) -> None:
    run = db.get(EvalRun, eval_run_id)
    if run is None:
        raise ValueError("评测任务不存在")
    dataset = db.get(EvalDataset, run.dataset_id)
    if dataset is None:
        raise ValueError("评测数据集不存在")

    run.status = TaskStatus.running
    run.error = ""
    db.commit()

    kb_ids = [uuid.UUID(k) for k in run.config.get("kb_ids", [])]
    top_k = run.config.get("top_k") or settings.top_k

    results: list[dict] = []
    for item in dataset.items:
        question = item.get("question", "").strip()
        expect_keywords: list[str] = item.get("expect_keywords") or []
        expect_doc: str = item.get("expect_doc") or ""
        if not question:
            continue

        entry: dict = {"question": question, "expect_doc": expect_doc}
        try:
            query_vector = embed_texts([question])[0]
            chunks = hybrid_retrieve(db, kb_ids, question, query_vector, top_k=top_k)

            retrieved_docs = [c.filename for c in chunks]
            entry["retrieved_docs"] = retrieved_docs
            entry["retrieval_hit"] = bool(expect_doc) and any(expect_doc in f for f in retrieved_docs)

            materials = [
                (i + 1, c.content, f"{c.filename} {location_label(c.meta)}".strip())
                for i, c in enumerate(chunks)
            ]
            materials_text = "\n\n".join(f"[{i}] {content}" for i, content, _ in materials)
            messages = build_chat_messages([], question, materials)
            answer = "".join(stream_chat(messages)) if chunks else ""
            entry["answer"] = answer

            if expect_keywords:
                hit = [kw for kw in expect_keywords if kw in answer]
                entry["keyword_hits"] = hit
                entry["keyword_rate"] = round(len(hit) / len(expect_keywords), 3)
            entry["scores"] = judge_answer(question, materials_text, answer) if answer else {
                "faithfulness": 0,
                "relevance": 0,
            }
        except Exception as e:  # noqa: BLE001 — one bad item must not kill the run
            logger.exception("eval item failed: %s", question)
            entry["error"] = str(e)
        results.append(entry)

    # ---- aggregate metrics ----
    total = len(results)
    retrieval_hits = sum(1 for r in results if r.get("retrieval_hit"))
    with_expect_doc = sum(1 for r in results if r.get("expect_doc"))
    keyword_rates = [r["keyword_rate"] for r in results if "keyword_rate" in r]
    faith = [r["scores"]["faithfulness"] for r in results if r.get("scores")]
    relev = [r["scores"]["relevance"] for r in results if r.get("scores")]

    run.metrics = {
        "total": total,
        "errors": sum(1 for r in results if r.get("error")),
        "retrieval_hit": retrieval_hits,
        "retrieval_precision": round(retrieval_hits / with_expect_doc, 3) if with_expect_doc else None,
        "avg_keyword_rate": round(sum(keyword_rates) / len(keyword_rates), 3) if keyword_rates else None,
        "avg_faithfulness": round(sum(faith) / len(faith), 2) if faith else None,
        "avg_relevance": round(sum(relev) / len(relev), 2) if relev else None,
    }
    run.results = results
    run.status = TaskStatus.done
    db.commit()
    logger.info("eval run %s done: %s", eval_run_id, run.metrics)
