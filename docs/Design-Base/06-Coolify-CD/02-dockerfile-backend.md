# 02-dockerfile-backend — Backend Dockerfile

> **何時讀**:寫 / 改 `backend/Dockerfile` 才讀。

multi-stage / `uv` 安裝 / 非 root / 含 `tzdata`(對齊 `00-overview/05-timezone.md`)。

---

## 模板

```Dockerfile
# syntax=docker/dockerfile:1.7

# ============ Stage 1: builder ============
FROM python:3.14.0-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1

# 安裝 uv(對齊 00-overview/01-versions.md uv 0.5.x)
COPY --from=ghcr.io/astral-sh/uv:0.5.18 /uv /usr/local/bin/uv

WORKDIR /app

# 先裝依賴(layer cache 友善)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# 再放 source
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

# ============ Stage 2: runtime ============
FROM python:3.14.0-slim

ENV TZ=Asia/Taipei \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# tzdata + curl(供 healthcheck)
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
```

---

## 規則

- **multi-stage**:builder 用完整工具裝依賴,runtime image 不帶 build tool
- **`uv sync --frozen`**:lock file 必逐字使用(對齊 `00-overview/01-versions.md`),`--no-dev` 跳過開發依賴
- **Python image tag**:`python:3.14.0-slim`(對齊 `00-overview/01-versions.md` Python 鎖定線)
- **uv image tag**:鎖到 patch(`ghcr.io/astral-sh/uv:0.5.18`),**禁** `latest`
- **`TZ=Asia/Taipei` + `tzdata`**:對齊 `00-overview/05-timezone.md`
- **非 root**:`useradd -r -u 1000`,**禁**以 root 跑 app
- **HEALTHCHECK**:image 內建,Coolify / compose 都認(`/api/v1/health` 對齊 `00-overview.md`)
- **EXPOSE 8000**:給 compose 連用,**不**等於對外開 port

## 不要做

- ❌ `pip install` / `poetry install`(對齊 `00-overview/01-versions.md` 禁裝清單)
- ❌ `COPY . .`(會帶進 `.env` / 測試 / `.git`,改用 `COPY app ./app` 精準)
- ❌ `ENV JWT_SECRET_KEY=...`(機密**禁**寫進 image,對齊 `04-env-and-secrets.md`)
- ❌ `USER root`(攻擊面 + 違反最小權限)
- ❌ build 階段執行 `alembic upgrade head`(部署時跑,見 `05-deploy-flow.md`)

## `.dockerignore`

```
.venv
__pycache__
*.pyc
.pytest_cache
.mypy_cache
.ruff_cache
.env*
!.env.*.example
.git
.github
tests/
docs/
```

## 多 worker / gunicorn

預設 `uvicorn` 單 process。需要多 worker → 走 gunicorn + uvicorn worker:

```Dockerfile
CMD ["gunicorn", "app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000"]
```

worker 數依 CPU 配額決定(`(2 × CPU) + 1` 為起跑線);效能調校見 `03-backend/08-performance.md`。
