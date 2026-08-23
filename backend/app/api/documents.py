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

    filename = Path(file.filename or "unnamed").name  # strip any path components
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
    db.flush()  # get doc.id

    # save file under uploads/{kb_id}/{doc_id}{ext}
    target_dir = settings.upload_path / str(kb_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{doc.id}{ext}"

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
    # store path relative to the upload root so it resolves on host and in containers
    doc.stored_path = f"{kb_id}/{doc.id}{ext}"
    db.commit()
    db.refresh(doc)
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
