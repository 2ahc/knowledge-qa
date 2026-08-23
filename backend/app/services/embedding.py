"""Embedding & LLM clients against the DashScope OpenAI-compatible endpoint."""
import logging
import time

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.dashscope_api_key:
            raise RuntimeError("DASHSCOPE_API_KEY 未配置")
        _client = OpenAI(api_key=settings.dashscope_api_key, base_url=settings.dashscope_base_url)
    return _client


def embed_texts(texts: list[str], batch_size: int | None = None) -> list[list[float]]:
    """Batch-embed texts with retry/backoff. Returns vectors in input order."""
    if not texts:
        return []
    client = get_client()
    batch_size = batch_size or settings.embed_batch
    results: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = client.embeddings.create(model=settings.embed_model, input=batch)
                results.extend([d.embedding for d in resp.data])
                last_err = None
                break
            except Exception as e:  # noqa: BLE001 — retry any transient error
                last_err = e
                wait = 2**attempt
                logger.warning("embedding batch %s failed (attempt %s): %s; retry in %ss", i, attempt + 1, e, wait)
                time.sleep(wait)
        if last_err is not None:
            raise RuntimeError(f"文本向量化失败: {last_err}")
    return results


def rerank(query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
    """Rerank documents against the query. Returns (original_index, score) sorted desc.

    Uses the DashScope rerank API (not part of the OpenAI-compatible surface).
    Falls back to original order when disabled or on failure.
    """
    if not settings.rerank_enabled or not documents:
        return [(i, 1.0) for i in range(len(documents))]
    import httpx

    try:
        resp = httpx.post(
            "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
            headers={"Authorization": f"Bearer {settings.dashscope_api_key}"},
            json={
                "model": settings.rerank_model,
                "input": {"query": query, "documents": documents},
                "parameters": {"top_n": top_n, "return_documents": False},
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data["output"]["results"]
        return sorted(((r["index"], r["relevance_score"]) for r in results), key=lambda x: -x[1])
    except Exception as e:  # noqa: BLE001
        logger.warning("rerank failed, falling back to retrieval order: %s", e)
        return [(i, 1.0) for i in range(min(top_n, len(documents)))]
