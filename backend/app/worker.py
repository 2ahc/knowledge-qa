"""Background worker loop: claims tasks from the DB queue and executes them.

Run standalone:  python -m app.worker
Or embedded in the FastAPI process via a daemon thread (see main.py lifespan).
"""
import logging
import time
import uuid

from app.db import SessionLocal
from app.models.task import TaskKind
from app.services import tasks as task_queue

logger = logging.getLogger(__name__)


def _handle(task_id: uuid.UUID, kind: TaskKind, payload: dict) -> None:
    db = SessionLocal()
    try:
        if kind in (TaskKind.document_index, TaskKind.document_reindex):
            from app.services.indexing import index_document

            index_document(db, uuid.UUID(payload["document_id"]))
        elif kind == TaskKind.eval_run:
            from app.services.eval import execute_eval_run

            execute_eval_run(db, uuid.UUID(payload["eval_run_id"]))
        else:
            raise ValueError(f"unknown task kind: {kind}")
        task_queue.mark_done(db, task_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("task %s failed", task_id)
        task_queue.mark_failed(db, task_id, str(e), requeue=True)
        # surface the error on the related domain object when applicable
        try:
            if kind in (TaskKind.document_index, TaskKind.document_reindex):
                from app.models.kb import DocStatus, Document

                doc = db.get(Document, uuid.UUID(payload["document_id"]))
                if doc is not None:
                    doc.status = DocStatus.failed
                    doc.error = str(e)[:2000]
                    db.commit()
            elif kind == TaskKind.eval_run:
                from app.models.eval import EvalRun
                from app.models.task import TaskStatus

                run = db.get(EvalRun, uuid.UUID(payload["eval_run_id"]))
                if run is not None:
                    run.status = TaskStatus.failed
                    run.error = str(e)[:2000]
                    db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("failed to record error on domain object")
    finally:
        db.close()


def run_worker_loop(poll_interval: float = 1.0) -> None:
    logger.info("worker started")
    db = SessionLocal()
    try:
        recovered = task_queue.recover_stale(db)
        if recovered:
            logger.info("recovered %s stale tasks", recovered)
    finally:
        db.close()

    while True:
        db = SessionLocal()
        try:
            task = task_queue.claim_next(db)
        finally:
            db.close()

        if task is None:
            time.sleep(poll_interval)
            continue

        logger.info("task %s (%s) claimed", task.id, task.kind.value)
        _handle(task.id, task.kind, task.payload)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run_worker_loop()
