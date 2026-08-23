# 企业知识问答库（Knowledge QA）

企业级知识问答系统（RAG）：上传企业文档 → 自动解析切片向量化 → 混合检索 + 大模型生成**带引用溯源**的回答。
支持多知识库、多用户权限、管理后台与问答效果评测，Docker Compose 一键部署。

## 架构

```
┌────────────┐   SSE    ┌──────────────────────────────────────┐
│ Vue3 前端  │◄────────►│ FastAPI 后端                          │
│ Element+   │  /api    │  auth / kbs / docs / chat / eval /   │
│ Pinia      │          │  admin / conversations               │
└────────────┘          └───────┬──────────────────────┬───────┘
                                │                      │
                        ┌───────▼───────┐      ┌───────▼────────┐
                        │ PostgreSQL 16 │      │ Worker（任务队列）│
                        │ + pgvector    │◄─────┤ 解析→切片→向量化 │
                        │ + pg_trgm     │      │ 评测运行         │
                        └───────────────┘      └───────┬────────┘
                                                       │
                                              ┌────────▼─────────┐
                                              │ 百炼 DashScope    │
                                              │ qwen-plus（生成）  │
                                              │ text-embedding-v4 │
                                              │ gte-rerank-v2     │
                                              └──────────────────┘
```

**检索策略**：向量检索（pgvector 余弦，top-50）+ 关键词检索（pg_trgm，top-20）→ RRF 融合 → `gte-rerank-v2` 重排 → 取 top-6 作为引用材料。检索为空时**不调用大模型**，直接如实告知，避免编造。

## 功能

- **文档管理**：PDF / Word / Excel / Markdown / TXT 上传，异步解析→切片→向量化，状态实时可见，失败可重试（重建索引）
- **智能问答**：SSE 流式输出、多轮会话记忆（自动裁剪历史）、回答带 [n] 引用标记 + 出处（文件名 / 页码 / 章节）
- **多知识库 + 权限**：私有 / 共享（成员+角色）/ 公开；admin / user 两级角色
- **管理后台**：用户管理、用量统计（提问量趋势、Token、延迟）、任务监控
- **问答评测**：评测集（JSONL：question / expect_keywords / expect_doc）→ 一键运行 → 检索命中率、关键词命中率、LLM 裁判忠实性/相关性评分

## 快速开始（本地开发）

前置：Python 3.11/3.12（推荐 [uv](https://docs.astral.sh/uv/)）、Node 20+、Docker（用于 PostgreSQL）。

```bash
# 1. 配置（复制并填入你的百炼 API Key）
cp .env.example .env
#    编辑 .env：DASHSCOPE_API_KEY=sk-xxxx（百炼控制台 → API-KEY 管理）

# 2. 启动数据库
docker compose up -d postgres

# 3. 后端（含内嵌 worker）
cd backend
uv sync
uv run alembic upgrade head          # 应用迁移
uv run python ../scripts/seed_demo.py  # 可选：管理员+示例知识库
uv run uvicorn app.main:app --port 8000

# 4. 前端
cd ../frontend
npm install
npm run dev                          # http://localhost:5173
```

打开 `http://localhost:5173`，使用 `admin / <seed 打印的密码>` 登录（若未跑 seed，用 `scripts/create_admin.py` 创建管理员）。

## Docker Compose 一键部署

```bash
cp .env.example .env   # 填入 DASHSCOPE_API_KEY，并修改 JWT_SECRET
docker compose up -d --build
cd backend && uv run python ../scripts/seed_demo.py   # 可选：种子数据
```

> **更换百炼 Key 后**：`docker compose up -d --force-recreate backend worker`（环境变量在容器创建时注入，必须重建容器才能生效）。

- 前端：`http://localhost:8090`
- 后端 API：`http://localhost:8000/api`（前端经 nginx 反代 `/api`，SSE 已配置不缓冲）
- 服务：`postgres`（pgvector:pg16）/ `backend` / `worker` / `frontend`

## 配置项（.env）

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://kqa:kqa_pass@127.0.0.1:5432/knowledge_qa` | PostgreSQL 连接 |
| `DASHSCOPE_API_KEY` | — | 百炼 API Key（必填） |
| `LLM_MODEL` | `qwen-plus` | 生成模型，可换 `qwen-max` / `qwen-turbo` |
| `EMBED_MODEL` | `text-embedding-v4` | 向量模型（1024 维） |
| `RERANK_MODEL` / `RERANK_ENABLED` | `gte-rerank-v2` / `true` | 重排模型开关 |
| `JWT_SECRET` | — | 生产环境务必更换（≥32 字符） |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `500` / `80` | 切片参数 |
| `TOP_K` | `6` | 每次问答引用的材料数 |
| `MAX_UPLOAD_MB` | `50` | 单文件大小上限 |

## 测试

```bash
cd backend
uv run pytest -v        # 38 个用例：鉴权/权限/上传/切片/解析/任务队列/检索/问答/评测/管理
```

测试使用同实例的 `knowledge_qa_test` 库（首次运行前：`docker exec kqa-postgres psql -U kqa -d knowledge_qa -c "CREATE DATABASE knowledge_qa_test;"`）。

## API 概览

| 模块 | 端点 |
|---|---|
| 认证 | `POST /api/auth/login` `refresh` `logout`，`GET /api/auth/me` |
| 用户 | `GET/POST /api/users`，`PATCH /api/users/{id}`（admin） |
| 知识库 | `GET/POST /api/kbs`，`PATCH/DELETE /api/kbs/{id}`，成员 `/members` |
| 文档 | `GET/POST /api/kbs/{id}/documents`，`DELETE`，`POST /{doc_id}/reindex` |
| 会话 | `GET/POST /api/conversations`，`PATCH/DELETE /{id}`，`GET /{id}/messages` |
| 问答 | `POST /api/chat`（SSE：`token` / `citations` / `done` / `error`） |
| 评测 | `GET/POST/DELETE /api/eval/datasets`，`POST/GET /api/eval/runs` |
| 管理 | `GET /api/admin/stats`，`GET /api/admin/tasks`（admin） |

## 已知限制（MVP）

- 扫描版 PDF（无文本层）不支持（无 OCR），上传时会给出明确失败原因
- 关键词检索基于 pg_trgm 三元组，对极短查询词效果一般（向量+重排兜底）
- 单机部署形态；任务队列为 DB 实现，横向扩展可平滑替换为 Celery/Redis

## 目录结构

```
knowledge-qa/
├── backend/            # FastAPI + SQLAlchemy + Alembic
│   ├── app/
│   │   ├── api/        # auth users kbs documents conversations chat eval admin
│   │   ├── core/       # security deps
│   │   ├── models/     # ORM（users kbs docs chunks convs msgs tasks eval）
│   │   ├── schemas/    # pydantic
│   │   ├── services/   # parsers chunking embedding retrieval llm indexing eval tasks
│   │   └── worker.py   # DB 任务队列消费者
│   ├── migrations/     # Alembic
│   └── tests/          # pytest（38）
├── frontend/           # Vue3 + TS + Vite + Pinia + Element Plus
├── deploy/nginx.conf   # SSE 友好的反代配置
├── scripts/            # create_admin / seed_demo
├── backend.Dockerfile / frontend.Dockerfile
└── docker-compose.yml  # postgres + backend + worker + frontend
```
