# 应用入口：创建 FastAPI 实例，注册所有路由。
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, chat, conversations, documents, eval, kbs, users
from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期钩子：启动时按需拉起内嵌 worker 线程。

    本地开发时 run_worker=true，API 进程内直接消费任务队列；
    生产部署（compose）里 run_worker=false，由独立的 worker 容器消费。
    """
    if settings.run_worker:
        from app.worker import run_worker_loop

        # daemon 线程：主进程退出时自动结束，不阻塞关闭
        thread = threading.Thread(target=run_worker_loop, daemon=True, name="kqa-worker")
        thread.start()
        logger.info("embedded worker thread started")
    yield


def create_app() -> FastAPI:
    """应用工厂：组装中间件、健康检查与全部业务路由。"""
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    # CORS：仅放行前端开发服务器（5173）。
    # 生产环境前端与后端同源（nginx 反代 /api），不会触发 CORS。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        """健康检查：部署探活与前端连通性验证用。"""
        return {"status": "ok", "app": settings.app_name}

    # 业务路由注册
    app.include_router(auth.router)  # 登录 / 刷新 / 登出 / 当前用户
    app.include_router(users.router)  # 用户管理（admin）与用户搜索
    app.include_router(kbs.router)  # 知识库 CRUD 与成员管理
    app.include_router(documents.router)  # 文档上传 / 删除 / 重建索引
    app.include_router(conversations.router)  # 会话管理
    app.include_router(chat.router)  # SSE 流式问答
    app.include_router(eval.router)  # 评测数据集与评测运行
    app.include_router(admin.router)  # 管理后台：统计与任务监控
    return app


app = create_app()
