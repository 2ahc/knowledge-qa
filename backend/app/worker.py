"""后台 worker：从数据库任务队列领取任务并执行。

启动方式二选一：
  1. 独立进程：python -m app.worker（compose 生产部署采用）
  2. 内嵌线程：API 进程内的 daemon 线程（本地开发，见 main.py lifespan）
"""
import logging
import time
import uuid

from app.db import SessionLocal
from app.models.task import TaskKind
from app.services import tasks as task_queue

logger = logging.getLogger(__name__)


def _handle(task_id: uuid.UUID, kind: TaskKind, payload: dict) -> None:
    """执行单个任务，并把成功/失败结果写回队列；失败时把错误同步到业务对象上，
    让用户在前端能看到具体原因（如文档状态变"失败"并带错误信息）。"""
    db = SessionLocal()
    try:
        # 按任务类型分发到具体处理函数（延迟导入，避免循环依赖）
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
        # mark_failed 内部会按重试策略决定是否重新入队（最多 3 次）
        task_queue.mark_failed(db, task_id, str(e), requeue=True)
        # 把错误信息落到关联的业务对象上，方便前端展示
        try:
            if kind in (TaskKind.document_index, TaskKind.document_reindex):
                from app.models.kb import DocStatus, Document

                doc = db.get(Document, uuid.UUID(payload["document_id"]))
                if doc is not None:
                    doc.status = DocStatus.failed
                    doc.error = str(e)[:2000]  # 截断超长错误，避免撑爆字段
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
    """worker 主循环：无限轮询任务队列，领到就执行，领不到就睡 1 秒。"""
    logger.info("worker started")
    # 启动时先回收僵死任务（上次进程崩溃时处于 running 的任务重新排队）
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
            # claim_next 使用 FOR UPDATE SKIP LOCKED 原子抢任务，
            # 多个 worker 并行也不会重复消费
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
