# 文档接口：上传 / 列表 / 重建索引 / 删除。
# 上传是"先落库入队、后台异步索引"模式：接口立即返回，
# 真正的解析与向量化由 worker 完成，前端轮询状态字段看进度。
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import can_edit_kb, get_accessible_kb, get_current_user
from app.db import get_db
from app.models.kb import DocStatus, Document
from app.models.task import TaskKind
from app.models.user import User
from app.schemas.kb import DocumentOut
from app.services import tasks as task_queue

router = APIRouter(prefix="/api/kbs/{kb_id}/documents", tags=["documents"])

# 允许上传的扩展名 → 解析器类型（见 services/parsers/__init__.py 的注册表）
ALLOWED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx", ".xlsx": "xlsx", ".md": "md", ".markdown": "md", ".txt": "txt"}


@router.get("", response_model=list[DocumentOut])
def list_documents(
    kb_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_accessible_kb(kb_id, user, db)
    stmt = select(Document).where(Document.kb_id == kb_id).order_by(Document.created_at.desc())
    return db.scalars(stmt).all()


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    kb_id: uuid.UUID,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = get_accessible_kb(kb_id, user, db)
    if not can_edit_kb(kb, user, db):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权向该知识库上传文档")

    filename = Path(file.filename or "unnamed").name  # 去掉路径成分，防止路径穿越
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"不支持的文件类型 '{ext}'，支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    doc = Document(
        kb_id=kb_id,
        filename=filename,
        filetype=ALLOWED_EXTENSIONS[ext],
        created_by=user.id,
        status="pending",
    )
    db.add(doc)
    db.flush()  # 先拿到 doc.id（用于文件名），但不提交

    # 文件落盘到 uploads/{kb_id}/{doc_id}{ext}：用 UUID 命名避免重名冲突
    target_dir = settings.upload_path / str(kb_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{doc.id}{ext}"

    # 流式写盘（每次读 1MB），边写边累计大小，超限立即中止并回滚
    size = 0
    max_bytes = settings.max_upload_mb * 1024 * 1024
    with target.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                db.delete(doc)
                db.commit()
                out.close()
                target.unlink(missing_ok=True)
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"文件超过 {settings.max_upload_mb}MB 限制")
            out.write(chunk)

    doc.size_bytes = size
    # 存相对路径（相对上传根目录），宿主机与容器内都能解析
    doc.stored_path = f"{kb_id}/{doc.id}{ext}"
    db.commit()
    db.refresh(doc)
    # 入队异步索引：接口到此返回，解析/向量化在 worker 中进行
    task_queue.enqueue(db, TaskKind.document_index, {"document_id": str(doc.id)})
    return doc


@router.post("/{doc_id}/reindex", response_model=DocumentOut)
def reindex_document(
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = get_accessible_kb(kb_id, user, db)
    if not can_edit_kb(kb, user, db):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权操作该知识库的文档")
    doc = db.get(Document, doc_id)
    if doc is None or doc.kb_id != kb_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    # 重建索引：重置状态并重新入队。索引流水线是幂等的（先删旧切片再写新切片）
    doc.status = DocStatus.pending
    doc.error = ""
    db.commit()
    db.refresh(doc)
    task_queue.enqueue(db, TaskKind.document_reindex, {"document_id": str(doc.id)})
    return doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = get_accessible_kb(kb_id, user, db)
    if not can_edit_kb(kb, user, db):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权删除该知识库的文档")
    doc = db.get(Document, doc_id)
    if doc is None or doc.kb_id != kb_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    if doc.stored_path:
        from app.services.indexing import resolve_stored_path

        resolve_stored_path(doc.stored_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
