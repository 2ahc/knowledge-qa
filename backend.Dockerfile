# 后端镜像：Python 3.12 + uv 管理依赖。
# backend 与 worker 两个 compose 服务共用本镜像（worker 只覆盖启动命令）。
FROM python:3.12-slim

WORKDIR /app

# 通过 pip 安装 uv；使用阿里云镜像源，适配国内网络
ENV UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv
RUN pip install --no-cache-dir uv

# 先复制依赖清单并安装：依赖不变时命中层缓存，大幅加速重复构建
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 再复制应用代码
COPY backend/ ./
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# 启动前先执行数据库迁移，再启动 API 服务（worker 由独立容器运行）
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
