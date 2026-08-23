"""Document indexing pipeline: parse -> chunk -> embed -> store."""
import logging
import uuid
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.models.kb import Chunk, DocStatus, Document
from app.services.chunking import chunk_segments
from app.services.embedding import embed_texts
from app.services.parsers import parse_document
from app.services.parsers.base import ParseError

logger = logging.getLogger(__name__)


class IndexingError(Exception):
    pass


def resolve_stored_path(stored_path: str) -> Path:
    """Resolve a document's stored path.

    New uploads store paths relative to the upload root so they resolve both on
    the host and inside containers; legacy rows may hold absolute paths.
    """
    p = Path(stored_path)
    if p.is_absolute() and p.exists():
        return p
    candidate = settings.upload_path / stored_path
    if candidate.exists() or not p.is_absolute():
        return candidate
    return p


def index_document(db: Session, document_id: uuid.UUID) -> None:
    """Full pipeline for one document. Raises IndexingError with a user-readable message."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise IndexingError("文档不存在")

    # --- parse ---
    doc.status = DocStatus.parsing
    doc.error = ""
    db.commit()
    try:
        segments = parse_document(doc.filetype, str(resolve_stored_path(doc.stored_path)))
    except ParseError:
        raise
    except Exception as e:  # noqa: BLE001
        raise IndexingError(f"文档解析失败: {e}")

    # --- chunk ---
    chunks = chunk_segments(segments)
    if not chunks:
        raise IndexingError("文档中没有可索引的内容")

    # --- embed ---
    doc.status = DocStatus.embedding
    db.commit()
    texts = [c.content for c in chunks]
    vectors = embed_texts(texts)

    # --- store (idempotent: replace previous chunks) ---
    db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    for spec, vector in zip(chunks, vectors):
        db.add(
            Chunk(
                document_id=doc.id,
                kb_id=doc.kb_id,
                content=spec.content,
                token_count=len(spec.content),
                meta=spec.meta,
                embedding=vector,
            )
        )
    doc.status = DocStatus.done
    doc.chunk_count = len(chunks)
    db.commit()
    logger.info("document %s indexed: %s chunks", doc.filename, len(chunks))
