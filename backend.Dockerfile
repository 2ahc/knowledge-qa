FROM python:3.12-slim

WORKDIR /app

# install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv

# dependencies first for layer caching
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# application code
COPY backend/ ./
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# migrate then serve (worker runs as a separate compose service)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
