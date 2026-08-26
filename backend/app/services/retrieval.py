# 混合检索：向量检索 + 关键词检索 → RRF 融合 → 重排，产出最终引用材料。
# 这是决定回答质量的核心环节。
import uuid
from dataclasses import dataclass

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.kb import Chunk, Document
from app.services.embedding import rerank


@dataclass
class RetrievedChunk:
    """一条检索命中的切片，携带引用展示所需的全部信息。"""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str  # 所属文档名（引用卡片标题）
    content: str  # 切片正文（送给大模型 + 引用卡片展示）
    meta: dict  # 出处元信息（页码/章节等）
    score: float  # 最终相关性得分


def location_label(meta: dict) -> str:
    """把切片元信息转成人类可读的出处描述，如「第 3 页 · 员工福利」。"""
    parts: list[str] = []
    if meta.get("page"):
        parts.append(f"第 {meta['page']} 页")
    if meta.get("sheet"):
        parts.append(f"工作表「{meta['sheet']}」")
    if meta.get("heading"):
        parts.append(f"「{meta['heading']}」")
    return " · ".join(parts)


def rrf_merge(ranked_lists: list[list[uuid.UUID]], k: int = 60) -> dict[uuid.UUID, float]:
    """RRF（Reciprocal Rank Fusion，倒数排名融合）：合并多路检索结果。

    公式：每个文档的得分 = Σ 1/(k + rank + 1)，rank 是它在每一路结果中的名次。
    只依赖"名次"不依赖"分数"，因此可以融合不同量纲的检索结果
    （向量余弦距离和 trigram 相似度无法直接比较，但名次可以）。
    k=60 是经典取值：削弱头部名次的过大优势，让多路都召回的文档胜出。
    """
    scores: dict[uuid.UUID, float] = {}
    for lst in ranked_lists:
        for rank, cid in enumerate(lst):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return scores


def hybrid_retrieve(
    db: Session,
    kb_ids: list[uuid.UUID],
    query: str,
    query_vector: list[float],
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """混合检索主流程：
    1) 向量检索（语义相似，粗排 50 条）
    2) 关键词检索（trigram 字面相似，粗排 20 条）——弥补向量对专有名词的不敏感
    3) RRF 融合两路结果，取前 20 候选
    4) 重排模型精排，取 top_k 条作为最终引用材料
    """
    top_k = top_k or settings.top_k
    if not kb_ids:
        return []

    # --- 第一路：向量检索（pgvector 余弦距离，走 HNSW 索引）---
    vec_stmt = (
        select(Chunk, Document.filename)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.kb_id.in_(kb_ids), Chunk.embedding.is_not(None))
        .order_by(Chunk.embedding.cosine_distance(query_vector))
        .limit(settings.vector_top_k)
    )
    vec_rows = db.execute(vec_stmt).all()

    # --- 第二路：关键词检索（pg_trgm 三元组相似度，走 GIN 索引）---
    sim = func.similarity(Chunk.content, query)
    kw_stmt = (
        select(Chunk, Document.filename)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.kb_id.in_(kb_ids), sim > 0.01)  # 过滤完全不相关的噪音
        .order_by(desc(sim))
        .limit(settings.keyword_top_k)
    )
    kw_rows = db.execute(kw_stmt).all()

    if not vec_rows and not kw_rows:
        return []

    # 去重合并：同一只切片可能被两路同时召回
    chunk_map: dict[uuid.UUID, tuple[Chunk, str]] = {}
    for chunk, filename in list(vec_rows) + list(kw_rows):
        chunk_map.setdefault(chunk.id, (chunk, filename))

    # RRF 融合两路名次，取融合分最高的 20 条进入重排
    rrf_scores = rrf_merge(
        [[c.id for c, _ in vec_rows], [c.id for c, _ in kw_rows]]
    )
    candidates = sorted(rrf_scores.items(), key=lambda x: -x[1])[:20]

    # --- 重排（精排）：cross-encoder 逐条打分，质量远高于粗排 ---
    if settings.rerank_enabled and candidates:
        docs = [chunk_map[cid][0].content for cid, _ in candidates]
        ranked = rerank(query, docs, top_k)
        final = [(candidates[idx][0], score) for idx, score in ranked]
    else:
        final = candidates[:top_k]

    # 组装最终结果
    results: list[RetrievedChunk] = []
    for cid, score in final:
        chunk, filename = chunk_map[cid]
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                filename=filename,
                content=chunk.content,
                meta=chunk.meta or {},
                score=round(float(score), 4),
            )
        )
    return results
