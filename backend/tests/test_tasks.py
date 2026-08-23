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

    # second claim gets t2, not the running t1
    claimed2 = task_queue.claim_next(db)
    assert claimed2.id == t2.id

    # queue empty now
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

    # exhaust attempts -> failed (attempts: 2, then 3 which fails the requeue)
    for _ in range(2):
        c = task_queue.claim_next(db)
        task_queue.mark_failed(db, c.id, "again", requeue=True)
    db.expire_all()
    final = db.get(type(t), t.id)
    assert final.status == TaskStatus.failed
    # nothing left to claim
    assert task_queue.claim_next(db) is None
