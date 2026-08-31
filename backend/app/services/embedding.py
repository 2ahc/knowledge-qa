"""向量化与模型调用客户端：对接百炼 DashScope（OpenAI 兼容端点）。"""
import logging
import time
from collections.abc import Callable

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """获取全局复用的 OpenAI 客户端（指向百炼兼容端点）。懒加载 + 单例。"""
    global _client
    if _client is None:
        if not settings.dashscope_api_key:
            raise RuntimeError("DASHSCOPE_API_KEY 未配置")
        _client = OpenAI(api_key=settings.dashscope_api_key, base_url=settings.dashscope_base_url)
    return _client


def embed_texts(
    texts: list[str],
    batch_size: int | None = None,
    on_batch: Callable[[int], None] | None = None,
) -> list[list[float]]:
    """批量文本向量化，带重试与指数退避。返回向量顺序与输入一致。

    - 分批调用（默认每批 10 条），避免单次请求过大；
    - 每批最多重试 3 次，等待 1s/2s/4s（指数退避），应对限流与瞬时故障；
    - on_batch(已完成条数)：每批成功后的回调，长任务用它刷心跳（见 indexing.py）。
    """
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
                # 校验返回条数与输入一致，防止接口异常时 zip 静默错位/丢数据
                if len(resp.data) != len(batch):
                    raise RuntimeError(
                        f"embedding 返回条数异常: 期望 {len(batch)} 条，实际 {len(resp.data)} 条"
                    )
                # 按 index 排序兜底（正常返回本就有序，防御接口乱序）
                results.extend([d.embedding for d in sorted(resp.data, key=lambda d: d.index)])
                last_err = None
                break
            except Exception as e:  # noqa: BLE001 — 任何瞬时错误都重试
                last_err = e
                wait = 2**attempt
                logger.warning("embedding batch %s failed (attempt %s): %s; retry in %ss", i, attempt + 1, e, wait)
                time.sleep(wait)
        if last_err is not None:
            raise RuntimeError(f"文本向量化失败: {last_err}")
        if on_batch is not None:
            on_batch(len(results))
    return results


def rerank(query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
    """用重排模型对候选文档按与查询的相关性精排。

    返回 [(原文档下标, 相关性得分), ...]，按得分降序。

    重排是"粗排之后的精排"：向量检索召回的 50 条只是大致相关，
    重排模型（cross-encoder）逐条判断相关性，显著提升最终 top_k 的质量。

    注意：重排接口是百炼原生 API，不在 OpenAI 兼容层内，故单独用 httpx 调用。
    关闭重排或调用失败时，退化为保持原检索顺序。
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
        # 重排失败不阻塞主流程：退回检索原序
        logger.warning("rerank failed, falling back to retrieval order: %s", e)
        return [(i, 1.0) for i in range(min(top_n, len(documents)))]
