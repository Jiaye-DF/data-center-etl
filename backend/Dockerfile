# syntax=docker/dockerfile:1.7
# FastAPI + uv multi-stage(docs/Design-Base/06-Coolify-CD/02-dockerfile-backend.md)
# 同一 image 供 backend / worker / scheduler 三服務共用(compose 以 command 區分)

# ============ Stage 1: builder ============
# Python 鎖 3.14.1(對齊 pyproject requires-python == 3.14.1.*;見 docs/Tasks/v1.1.0/fixed.md)
FROM python:3.14.1-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1

# uv 鎖到 patch,禁 latest;uv.lock 為 revision 3 格式,需 0.8+,故鎖 0.11.20(見 fixed.md)
COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /usr/local/bin/uv

WORKDIR /app

# 先裝依賴(layer cache 友善)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# 再放 source(精準 COPY,禁 COPY . .)
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

# ============ Stage 2: runtime ============
FROM python:3.14.1-slim

ENV TZ=Asia/Taipei \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# tzdata + curl(供 healthcheck;TZ 對齊 00-overview/05-timezone.md)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata curl \
    && ln -sf /usr/share/zoneinfo/$TZ /etc/localtime \
    && rm -rf /var/lib/apt/lists/*

# 非 root
RUN useradd -r -u 1000 -m appuser
WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
