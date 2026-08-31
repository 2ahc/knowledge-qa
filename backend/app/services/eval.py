# 评测执行器：对评测集逐题跑"检索→生成→打分"，汇总四类指标。
#
# 指标含义：
#   检索命中率   —— 期望文档是否出现在检索结果里（衡量检索质量）
#   关键词命中率 —— 期望关键词是否出现在回答里（衡量回答覆盖度）
#   忠实性/相关性 —— LLM 裁判打分（衡量回答质量）
import logging
import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.models.eval import EvalDataset, EvalRun
from app.models.task import TaskStatus
from app.services import tasks as task_queue
from app.services.embedding import embed_texts
from app.services.llm import build_chat_messages, complete_chat, judge_answer
from app.services.retrieval import hybrid_retrieve, location_label

logger = logging.getLogger(__name__)


def execute_eval_run(db: Session, eval_run_id: uuid.UUID, task_id: uuid.UUID | None = None) -> None:
    """执行一次完整评测。由 worker 以异步任务方式调用。

    task_id：任务队列的任务 ID（worker 调用时传入）。评测逐题执行、耗时较长，
    每题结束刷一次心跳，避免被僵死回收误杀。
    """
    run = db.get(EvalRun, eval_run_id)
    if run is None:
        raise ValueError("评测任务不存在")
    dataset = db.get(EvalDataset, run.dataset_id)
    if dataset is None:
        raise ValueError("评测数据集不存在")
    hb = task_queue.Heartbeat(db, task_id)

    run.status = TaskStatus.running
    run.error = ""
    db.commit()

    kb_ids = [uuid.UUID(k) for k in run.config.get("kb_ids", [])]
    top_k = run.config.get("top_k") or settings.top_k

    # ---- 逐题评测 ----
    results: list[dict] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    for item in dataset.items:
        question = item.get("question", "").strip()
        expect_keywords: list[str] = item.get("expect_keywords") or []
        expect_doc: str = item.get("expect_doc") or ""
        if not question:
            continue

        entry: dict = {"question": question, "expect_doc": expect_doc}
        try:
            # 1) 与线上问答完全一致的检索链路（保证评的就是真实链路）
            query_vector = embed_texts([question])[0]
            chunks = hybrid_retrieve(db, kb_ids, question, query_vector, top_k=top_k)

            # 2) 检索命中判断：期望文档名（子串匹配）是否出现在召回结果里
            retrieved_docs = [c.filename for c in chunks]
            entry["retrieved_docs"] = retrieved_docs
            entry["retrieval_hit"] = bool(expect_doc) and any(expect_doc in f for f in retrieved_docs)

            # 3) 生成回答：评测是批量场景，用非流式补全（比流式更快更省连接）
            materials = [
                (i + 1, c.content, f"{c.filename} {location_label(c.meta)}".strip())
                for i, c in enumerate(chunks)
            ]
            materials_text = "\n\n".join(f"[{i}] {content}" for i, content, _ in materials)
            messages = build_chat_messages([], question, materials)
            answer, usage = complete_chat(messages) if chunks else ("", {})
            total_prompt_tokens += usage.get("prompt_tokens", 0)
            total_completion_tokens += usage.get("completion_tokens", 0)
            entry["answer"] = answer

            # 4) 关键词命中：期望关键词出现在回答中的比例
            if expect_keywords:
                hit = [kw for kw in expect_keywords if kw in answer]
                entry["keyword_hits"] = hit
                entry["keyword_rate"] = round(len(hit) / len(expect_keywords), 3)
            # 5) LLM 裁判打分
            entry["scores"] = judge_answer(question, materials_text, answer) if answer else {
                "faithfulness": 0,
                "relevance": 0,
            }
        except Exception as e:  # noqa: BLE001 — 单题失败不中断整个评测
            logger.exception("eval item failed: %s", question)
            entry["error"] = str(e)
        results.append(entry)
        hb.beat()  # 每题刷一次心跳

    # ---- 汇总指标 ----
    total = len(results)
    retrieval_hits = sum(1 for r in results if r.get("retrieval_hit"))
    with_expect_doc = sum(1 for r in results if r.get("expect_doc"))  # 只统计设置了期望文档的题
    keyword_rates = [r["keyword_rate"] for r in results if "keyword_rate" in r]
    faith = [r["scores"]["faithfulness"] for r in results if r.get("scores")]
    relev = [r["scores"]["relevance"] for r in results if r.get("scores")]

    run.metrics = {
        "total": total,
        "errors": sum(1 for r in results if r.get("error")),
        "retrieval_hit": retrieval_hits,
        # 检索命中率 = 命中数 / 设置了期望文档的题数
        "retrieval_precision": round(retrieval_hits / with_expect_doc, 3) if with_expect_doc else None,
        "avg_keyword_rate": round(sum(keyword_rates) / len(keyword_rates), 3) if keyword_rates else None,
        "avg_faithfulness": round(sum(faith) / len(faith), 2) if faith else None,
        "avg_relevance": round(sum(relev) / len(relev), 2) if relev else None,
        # 本次评测消耗的 token 总量（生成回答部分，不含裁判调用）
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
    }
    run.results = results
    run.status = TaskStatus.done
    db.commit()
    logger.info("eval run %s done: %s", eval_run_id, run.metrics)
