# 应用入口：创建 FastAPI 实例，注册所有路由。
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, chat, conversations, documents, eval, kbs, users
from app.config import settings

logger = logging.getLogger(__name__)

# JWT 默认密钥：仅本地开发可用。生产漏配 .env 时所有令牌都可被伪造，
# 因此在非 debug 模式下启动即失败，把配置错误挡在上线之前
_DEFAULT_JWT_SECRET = "change-me-in-production"


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
    # 密钥防漏配：生产模式（debug=false）下使用默认密钥直接拒绝启动
    if settings.jwt_secret == _DEFAULT_JWT_SECRET:
        if not settings.debug:
            raise RuntimeError("JWT_SECRET 未配置：生产环境禁止使用默认密钥，请在 .env 中设置")
        logger.warning("JWT_SECRET 仍为默认值，仅限本地开发；生产部署前必须更换")

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

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        """访问日志：记录方法/路径/状态码/耗时，排查线上问题的第一手信息。
        健康检查高频探活，不打日志。"""
        start = time.perf_counter()
        response = await call_next(request)
        if not request.url.path.startswith("/api/health"):
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "%s %s -> %s (%.1fms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
        return response

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
