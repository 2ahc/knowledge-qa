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
    if settings.run_worker:
        from app.worker import run_worker_loop

        thread = threading.Thread(target=run_worker_loop, daemon=True, name="kqa-worker")
        thread.start()
        logger.info("embedded worker thread started")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok", "app": settings.app_name}

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(kbs.router)
    app.include_router(documents.router)
    app.include_router(conversations.router)
    app.include_router(chat.router)
    app.include_router(eval.router)
    app.include_router(admin.router)
    return app


app = create_app()
