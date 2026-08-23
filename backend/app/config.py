from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "Knowledge QA"
    debug: bool = True

    # Database
    database_url: str = "postgresql+psycopg://kqa:kqa_pass@127.0.0.1:5432/knowledge_qa"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 120
    refresh_token_days: int = 7

    # Bailian / DashScope
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-plus"
    embed_model: str = "text-embedding-v4"
    rerank_model: str = "gte-rerank-v2"
    rerank_enabled: bool = True

    # Indexing
    chunk_size: int = 500
    chunk_overlap: int = 80
    embed_batch: int = 10
    max_upload_mb: int = 50
    max_chunks_per_doc: int = 4000
    upload_dir: str = "uploads"

    # Retrieval
    top_k: int = 6
    vector_top_k: int = 50
    keyword_top_k: int = 20

    # Tasks
    task_stale_minutes: int = 30
    run_worker: bool = True  # embedded worker thread in the API process

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        if not p.is_absolute():
            p = PROJECT_ROOT / "backend" / self.upload_dir
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
