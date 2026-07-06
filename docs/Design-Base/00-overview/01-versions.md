# 01-versions — 版本鎖定 + 套件清單

> **何時讀**:加套件 / 升版 / 啟動新專案。本檔為**版本 + 套件清單**的 single source,其他檔案**不重述**;禁裝 / 使用規則對應 `02-frontend` / `03-backend` / `04-databases` / `90-third-party-service`。

---

## 強制鎖定(硬底線)

| 項目 | 鎖定線 | lock 範例 |
| --- | --- | --- |
| React | **`19.2.x`** | `19.2.0` |
| Python | **`3.14.x`** | `3.14.1` |
| Node.js | 24.x LTS | `24.14.0` |
| PostgreSQL | 18.x | `18`(`postgres:${POSTGRES_VERSION}-alpine`,env 注入)|
| Redis | 8.8.x | `8.8.0`(`redis:8.8.0-alpine`)|

採用方專案**禁**自行降版;跨 minor 由本檔發動,採用方追隨。密碼雜湊採 `bcrypt` 直呼(v1.1.0 起移除 passlib,鎖版組合不相容,見 `docs/Tasks/v1.1.0/fixed.md §3`)。

---

## 鎖定原則

- **禁**浮動版本(`^` / `~` / `*` / `latest` / `>=`),一律 `MAJOR.MINOR.PATCH`
- `engines.node` / `requires-python` 同樣鎖到 patch
- 服務版本於 `.env` 用 `<SERVICE>_VERSION` 變數,`docker-compose.yml` 用 `${POSTGRES_VERSION}` 引用,**禁**直寫 image tag
- 升版**獨立 commit**:`(AI?) Modify: 升級 <套件> 從 <舊> 至 <新>(<理由>)`,同 commit 含本表 + lock file +(若涉)`.env`

---

## Frontend 套件(`frontend/package.json`)

| 套件 | 鎖定線 | lock 範例 |
| --- | --- | --- |
| `react` / `react-dom` | 19.2.x | `19.2.0` |
| `@types/react` / `@types/react-dom` | 19.1.x | `19.1.6` / `19.1.5` |
| `typescript` | 5.x | `5.9.3` |
| `@types/node` | 24.x | `24.0.0` |
| `next` *(Next 路線)* | 16.2.x | `16.2.7` |
| `@reduxjs/toolkit` | 2.x | `2.11.2` |
| `react-redux` | 9.x | `9.2.0` |
| `tailwindcss` + `@tailwindcss/postcss` | 4.x | `4.2.4`(`tailwindcss` 與 plugin 版本必相等)|
| `postcss` | 8.x | `8.5.12` |
| `eslint` / `eslint-config-next` | 9.x / 16.2.x | `9.39.4` / `16.2.7` |
| `@eslint/eslintrc` | 3.x | `3.2.0` |

> 前端套件 Sources of Truth 為 `frontend/package.json` / `frontend/package-lock.json`,本表為登記快照;新增依賴時**須同步本表**。
> Tailwind plugin:Vite 路線用 `@tailwindcss/vite`,Next 路線用 `@tailwindcss/postcss`。i18n / 日期 / 測試套件視專案需要,加入時補進本表。

---

## Backend 套件(`backend/pyproject.toml`)

| 套件 | 鎖定線 | lock 範例 |
| --- | --- | --- |
| Python | 3.14.x | `3.14.1`(`requires-python = "==3.14.1.*"`)|
| `fastapi` | 0.136.x | `0.136.1` |
| `uvicorn[standard]` | 0.46.x | `0.46.0` |
| `pydantic` / `pydantic-settings` | 2.13.x / 2.14.x | `2.13.3` / `2.14.0` |
| `sqlalchemy[asyncio]` | 2.0.x | `2.0.49` |
| `asyncpg` | 0.31.x | `0.31.0` |
| `alembic` | 1.14.x | `1.14.0` |
| `pyjwt[crypto]` | 2.x | `2.10.1` |
| `bcrypt` | 5.0.x | `5.0.0` |
| `httpx` | 0.28.x | `0.28.1` |
| `taskiq` | 0.12.x | `0.12.4` |
| `taskiq-redis` | 1.2.x | `1.2.3` |
| `pyyaml` | 6.0.x | `6.0.3` |
| `tzdata` | 2026.x | `2026.2` |
| `python-multipart` | 0.0.x | `0.0.20` |
| `pip-audit` | 2.8.x | `2.8.0` |
| `pytest` / `pytest-asyncio` / `respx` | 8.x / 1.4.x / 0.23.x | `8.4.2` / `1.4.0` / `0.23.1` |
| `types-pyyaml` | 6.0.x | `6.0.12.20260518` |
| `ruff` / `mypy` | 0.15.x / 1.20.x | `0.15.20` / `1.20.2` |
| `uv`(唯一 package manager) | 0.11.x | `0.11.20` |

> 套件實際版本以 `backend/pyproject.toml` / `backend/uv.lock` 為 Sources of Truth,本表為登記快照;新增依賴時**須同步本表**。
> Log 套件(`loguru` 或 stdlib `logging`)二擇一,加入時補進本表;細節見 `03-backend/05-exceptions-and-logging.md`。

---

## Sources of Truth

本檔「lock 範例」與下列 lock file 必**逐字一致**:

- `frontend/package-lock.json`(或 `pnpm-lock.yaml`)
- `backend/uv.lock`
- `.env` 的 `<SERVICE>_VERSION`(例 `POSTGRES_VERSION=18`)

不一致時:**以 lock / `.env` 為準**,立即修本表。

---

## 升版流程

1. 升版理由(security / bug / 需求);**禁**「順手升一下」
2. 獨立 commit + 同 commit 含:本表 + lock file +(若涉)`.env*` / `docker-compose.yml`
3. 跨 major(React 19→20 / SQLAlchemy 2→3 / Python 3.14→3.15)→ 先寫 `docs/Tasks/v*/propose-v*.md` 評估 breaking,**禁**單一 commit 帶過
