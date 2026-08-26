# 文档索引流水线：解析 → 切片 → 向量化 → 入库。
# 由 worker 异步调用（见 worker.py），全程更新文档状态供前端轮询。
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
    """索引失败异常：消息是用户可读的中文原因，会记录到文档的 error 字段。"""


def resolve_stored_path(stored_path: str) -> Path:
    """解析文档的物理存储路径。

    新上传的文档存的是"相对上传根目录"的路径（如 "kb_id/doc_id.md"），
    这样在宿主机和容器内都能正确解析；历史数据可能是绝对路径，做兼容处理。
    """
    p = Path(stored_path)
    if p.is_absolute() and p.exists():
        return p
    candidate = settings.upload_path / stored_path
    if candidate.exists() or not p.is_absolute():
        return candidate
    return p


def index_document(db: Session, document_id: uuid.UUID) -> None:
    """单个文档的完整索引流水线。失败抛 IndexingError（含用户可读原因）。

    流程分四步，每步都会更新文档状态（前端轮询可见进度）：
      parsing(解析) → 切片 → embedding(向量化) → 写入数据库
    """
    doc = db.get(Document, document_id)
    if doc is None:
        raise IndexingError("文档不存在")

    # --- 第 1 步：解析 --- 按文件类型选解析器，产出"带出处元信息的文本段"
    doc.status = DocStatus.parsing
    doc.error = ""
    db.commit()
    try:
        segments = parse_document(doc.filetype, str(resolve_stored_path(doc.stored_path)))
    except ParseError:
        raise
    except Exception as e:  # noqa: BLE001
        raise IndexingError(f"文档解析失败: {e}")

    # --- 第 2 步：切片 --- 递归切分 + 重叠（见 chunking.py）
    chunks = chunk_segments(segments)
    if not chunks:
        raise IndexingError("文档中没有可索引的内容")

    # --- 第 3 步：向量化 --- 批量调用百炼 embedding 接口（耗时最长的一步）
    doc.status = DocStatus.embedding
    db.commit()
    texts = [c.content for c in chunks]
    vectors = embed_texts(texts)

    # --- 第 4 步：入库 --- 幂等设计：先删旧切片再写新切片，
    # 因此"重建索引"可以安全地重复执行，不会产生脏数据
    db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    for spec, vector in zip(chunks, vectors):
        db.add(
            Chunk(
                document_id=doc.id,
                kb_id=doc.kb_id,
                content=spec.content,
                token_count=len(spec.content),
                meta=spec.meta,  # 页码/章节等出处信息，引用溯源用
                embedding=vector,
            )
        )
    doc.status = DocStatus.done
    doc.chunk_count = len(chunks)
    db.commit()
    logger.info("document %s indexed: %s chunks", doc.filename, len(chunks))
