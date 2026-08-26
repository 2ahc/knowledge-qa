# 全局配置：所有配置项均可被环境变量覆盖（pydantic-settings 自动完成）。
# 加载顺序：进程环境变量 > 项目根目录 .env > 代码里的默认值。
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（本文件位于 backend/app/config.py，向上三级即仓库根）
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略 .env 里未声明的变量，避免启动报错
    )

    # ---- 应用 ----
    app_name: str = "Knowledge QA"
    debug: bool = True

    # ---- 数据库（PostgreSQL + pgvector）----
    database_url: str = "postgresql+psycopg://kqa:kqa_pass@127.0.0.1:5432/knowledge_qa"

    # ---- 认证（JWT）----
    jwt_secret: str = "change-me-in-production"  # 生产环境必须更换
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 120  # 访问令牌有效期（小时级，用于常规请求）
    refresh_token_days: int = 7  # 刷新令牌有效期（用于无感续期）

    # ---- 百炼 / DashScope（模型服务）----
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-plus"  # 生成回答的大模型
    embed_model: str = "text-embedding-v4"  # 文本向量化模型（1024 维）
    rerank_model: str = "gte-rerank-v2"  # 重排模型
    rerank_enabled: bool = True  # 关闭后仅用向量+关键词融合结果

    # ---- 索引（文档切片与向量化）----
    chunk_size: int = 500  # 单个切片的最大字符数
    chunk_overlap: int = 80  # 相邻切片的重叠字符数（避免语义被截断）
    embed_batch: int = 10  # 每次调用向量化接口的文本条数上限
    max_upload_mb: int = 50  # 单文件上传大小上限
    max_chunks_per_doc: int = 4000  # 单文档最大切片数（防止超大文档拖垮系统）
    upload_dir: str = "uploads"  # 上传文件根目录（相对或绝对路径均可）

    # ---- 检索 ----
    top_k: int = 6  # 最终送给大模型的引用材料条数
    vector_top_k: int = 50  # 向量检索召回条数（粗排）
    keyword_top_k: int = 20  # 关键词检索召回条数（粗排）

    # ---- 任务队列 ----
    task_stale_minutes: int = 30  # 任务心跳超时时间，超时视为僵死并重新入队
    run_worker: bool = True  # 是否在 API 进程内启动内嵌 worker 线程

    @property
    def upload_path(self) -> Path:
        """上传根目录的绝对路径。相对路径按 项目根/backend/ 解析；不存在则自动创建。"""
        p = Path(self.upload_dir)
        if not p.is_absolute():
            p = PROJECT_ROOT / "backend" / self.upload_dir
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
