from app.models.task import TaskKind, TaskStatus
from app.services import tasks as task_queue


def test_enqueue_and_claim(db):
    t1 = task_queue.enqueue(db, TaskKind.document_index, {"document_id": "a"})
    t2 = task_queue.enqueue(db, TaskKind.document_index, {"document_id": "b"})

    claimed = task_queue.claim_next(db)
    assert claimed is not None and claimed.id == t1.id
    assert claimed.status == TaskStatus.running
    assert claimed.attempts == 1
    assert claimed.heartbeat_at is not None

    # 第二次领取拿到的是 t2（t1 已在运行中，SKIP LOCKED 语义）
    claimed2 = task_queue.claim_next(db)
    assert claimed2.id == t2.id

    # 队列已空
    assert task_queue.claim_next(db) is None

    task_queue.mark_done(db, t1.id)
    db.expire_all()
    assert db.get(type(t1), t1.id).status == TaskStatus.done


def test_mark_failed_with_requeue(db):
    t = task_queue.enqueue(db, TaskKind.document_index, {"document_id": "x"})
    claimed = task_queue.claim_next(db)
    task_queue.mark_failed(db, claimed.id, "boom", requeue=True)
    db.expire_all()
    fresh = db.get(type(t), t.id)
    assert fresh.status == TaskStatus.queued
    assert "boom" in fresh.error

    # 耗尽重试次数（共 3 次尝试）后彻底失败，不再入队
    for _ in range(2):
        c = task_queue.claim_next(db)
        task_queue.mark_failed(db, c.id, "again", requeue=True)
    db.expire_all()
    final = db.get(type(t), t.id)
    assert final.status == TaskStatus.failed
    # 队列里没有可领取的任务了
    assert task_queue.claim_next(db) is None
