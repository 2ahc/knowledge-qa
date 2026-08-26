# 评测接口：评测集（题目）与评测运行（发起/查询）。
# 评测是重操作（逐题检索+生成+裁判打分），因此发起运行走异步任务队列，
# 前端轮询 GET /runs/{id} 看进度。
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_accessible_kb, get_current_user
from app.db import get_db
from app.models.eval import EvalDataset, EvalRun
from app.models.task import TaskKind
from app.models.user import User
from app.schemas.eval import EvalDatasetCreate, EvalDatasetOut, EvalRunCreate, EvalRunOut
from app.services import tasks as task_queue

router = APIRouter(prefix="/api/eval", tags=["eval"])


@router.get("/datasets", response_model=list[EvalDatasetOut])
def list_datasets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(EvalDataset).where(EvalDataset.created_by == user.id).order_by(EvalDataset.created_at.desc())
    return db.scalars(stmt).all()


@router.post("/datasets", response_model=EvalDatasetOut, status_code=status.HTTP_201_CREATED)
def create_dataset(
    body: EvalDatasetCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 前置校验：每条评测项必须有 question
    for i, item in enumerate(body.items):
        if not item.get("question"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"第 {i + 1} 条评测项缺少 question 字段")
    ds = EvalDataset(name=body.name, items=body.items, created_by=user.id)
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ds = db.get(EvalDataset, dataset_id)
    if ds is None or ds.created_by != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "数据集不存在")
    db.delete(ds)
    db.commit()


@router.get("/runs", response_model=list[EvalRunOut])
def list_runs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(EvalRun).where(EvalRun.created_by == user.id).order_by(EvalRun.created_at.desc())
    return db.scalars(stmt).all()


@router.post("/runs", response_model=EvalRunOut, status_code=status.HTTP_201_CREATED)
def create_run(
    body: EvalRunCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ds = db.get(EvalDataset, body.dataset_id)
    if ds is None or ds.created_by != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "数据集不存在")
    for kb_id in body.kb_ids:
        get_accessible_kb(kb_id, user, db)

    run = EvalRun(
        dataset_id=ds.id,
        config={"kb_ids": [str(k) for k in body.kb_ids], "top_k": body.top_k},
        created_by=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    # 入队异步执行：接口立即返回，worker 负责真正的评测
    task_queue.enqueue(db, TaskKind.eval_run, {"eval_run_id": str(run.id)})
    return run


@router.get("/runs/{run_id}")
def get_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.get(EvalRun, run_id)
    if run is None or run.created_by != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "评测运行不存在")
    out = EvalRunOut.model_validate(run).model_dump()
    out["results"] = run.results
    return out
