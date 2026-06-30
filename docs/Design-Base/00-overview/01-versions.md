# 01-versions — 版本鎖定 + 套件清單

> **何時讀**:加套件 / 升版 / 啟動新專案。本檔為**版本 + 套件清單**的 single source,其他檔案**不重述**;禁裝 / 使用規則對應 `02-frontend` / `03-backend` / `04-databases` / `90-third-party-service`。

---

## 強制鎖定(硬底線)

| 項目 | 鎖定線 | lock 範例 |
| --- | --- | --- |
| React | **`19.2.x`** | `19.2.5` |
| Python | **`3.14.x`** | `3.14.0` |
| Node.js | 22.x LTS | `22.13.0` |
| PostgreSQL | 17.x | `17.2` |

採用方專案**禁**自行降版;跨 minor 由本檔發動,採用方追隨。Python 3.14 下 `passlib 1.7.4` 走 bcrypt path,接受 `crypt` 模組告警風險。

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
| `react` / `react-dom` | 19.2.x | `19.2.5` |
| `@types/react` / `@types/react-dom` | 19.2.x | `19.2.0` |
| `typescript` | 5.x | `5.7.3` |
| `vite` *(Vite 路線)* | 6.x | `6.0.7` |
| `@vitejs/plugin-react` *(Vite 路線)* | 4.x | `4.3.4` |
| `react-router-dom` *(Vite 路線)* | 7.x | `7.1.1` |
| `next` *(Next 路線,擇一)* | 15.x | `15.1.4` |
| `@reduxjs/toolkit` | 2.x | `2.5.0` |
| `react-redux` | 9.x | `9.2.0` |
| `tailwindcss` + 對應 plugin | 4.x | `4.0.0`(`tailwindcss` 與 plugin 版本必相等)|
| `vitest` / `@testing-library/react` | 2.x / 16.x | `2.1.8` / `16.1.0` |
| `eslint` + `@typescript-eslint/*` | 9.x / 8.x | `9.18.0` / `8.20.0` |
| `prettier` | 3.x | `3.4.2` |

> Tailwind plugin:Vite 路線用 `@tailwindcss/vite`,Next 路線用 `@tailwindcss/postcss`。i18n / 日期套件視專案需要,加入時補進本表。

---

## Backend 套件(`backend/pyproject.toml`)

| 套件 | 鎖定線 | lock 範例 |
| --- | --- | --- |
| Python | 3.14.x | `3.14.0`(`requires-python = "==3.14.*"`)|
| `fastapi` | 0.115.x | `0.115.6` |
| `uvicorn[standard]` | 0.34.x | `0.34.0` |
| `pydantic` / `pydantic-settings` | 2.10.x / 2.7.x | `2.10.5` / `2.7.1` |
| `sqlalchemy` | 2.0.x | `2.0.36` |
| `asyncpg` | 0.30.x | `0.30.0` |
| `alembic` | 1.14.x | `1.14.0` |
| `pyjwt[crypto]` | 2.x | `2.10.1` |
| `passlib[bcrypt]` | 1.7.x | `1.7.4` |
| `httpx` | 0.28.x | `0.28.1` |
| `pytest` / `pytest-asyncio` / `respx` | 8.x / 0.25.x / 0.22.x | `8.3.4` / `0.25.2` / `0.22.0` |
| `ruff` / `mypy` | 0.9.x / 1.14.x | `0.9.2` / `1.14.1` |
| `uv`(唯一 package manager) | 0.5.x | `0.5.18` |

> Log 套件(`loguru` 或 stdlib `logging`)二擇一,加入時補進本表;細節見 `03-backend/05-exceptions-and-logging.md`。

---

## Sources of Truth

本檔「lock 範例」與下列 lock file 必**逐字一致**:

- `frontend/package-lock.json`(或 `pnpm-lock.yaml`)
- `backend/uv.lock`
- `.env` 的 `<SERVICE>_VERSION`(例 `POSTGRES_VERSION=17.2`)

不一致時:**以 lock / `.env` 為準**,立即修本表。

---

## 升版流程

1. 升版理由(security / bug / 需求);**禁**「順手升一下」
2. 獨立 commit + 同 commit 含:本表 + lock file +(若涉)`.env*` / `docker-compose.yml`
3. 跨 major(React 19→20 / SQLAlchemy 2→3 / Python 3.14→3.15)→ 先寫 `docs/Tasks/v*/propose-v*.md` 評估 breaking,**禁**單一 commit 帶過
