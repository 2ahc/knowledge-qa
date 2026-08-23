import uuid
from dataclasses import dataclass

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.kb import Chunk, Document
from app.services.embedding import rerank


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    content: str
    meta: dict
    score: float


def location_label(meta: dict) -> str:
    """Human-readable citation location from chunk metadata."""
    parts: list[str] = []
    if meta.get("page"):
        parts.append(f"第 {meta['page']} 页")
    if meta.get("sheet"):
        parts.append(f"工作表「{meta['sheet']}」")
    if meta.get("heading"):
        parts.append(f"「{meta['heading']}」")
    return " · ".join(parts)


def rrf_merge(ranked_lists: list[list[uuid.UUID]], k: int = 60) -> dict[uuid.UUID, float]:
    """Reciprocal Rank Fusion across ranked id lists."""
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
    """Vector search + trigram keyword search, RRF-merged, then reranked."""
    top_k = top_k or settings.top_k
    if not kb_ids:
        return []

    # --- vector leg ---
    vec_stmt = (
        select(Chunk, Document.filename)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.kb_id.in_(kb_ids), Chunk.embedding.is_not(None))
        .order_by(Chunk.embedding.cosine_distance(query_vector))
        .limit(settings.vector_top_k)
    )
    vec_rows = db.execute(vec_stmt).all()

    # --- keyword leg (pg_trgm similarity) ---
    sim = func.similarity(Chunk.content, query)
    kw_stmt = (
        select(Chunk, Document.filename)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.kb_id.in_(kb_ids), sim > 0.01)
        .order_by(desc(sim))
        .limit(settings.keyword_top_k)
    )
    kw_rows = db.execute(kw_stmt).all()

    if not vec_rows and not kw_rows:
        return []

    chunk_map: dict[uuid.UUID, tuple[Chunk, str]] = {}
    for chunk, filename in list(vec_rows) + list(kw_rows):
        chunk_map.setdefault(chunk.id, (chunk, filename))

    rrf_scores = rrf_merge(
        [[c.id for c, _ in vec_rows], [c.id for c, _ in kw_rows]]
    )
    candidates = sorted(rrf_scores.items(), key=lambda x: -x[1])[:20]

    # --- rerank ---
    if settings.rerank_enabled and candidates:
        docs = [chunk_map[cid][0].content for cid, _ in candidates]
        ranked = rerank(query, docs, top_k)
        final = [(candidates[idx][0], score) for idx, score in ranked]
    else:
        final = candidates[:top_k]

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
