# AGENTS.md — data-center-etl

跨工具(Claude Code / Codex / Cursor / Cline / Aider)agent 協議。**鎖定 Next.js (App Router) + TypeScript + FastAPI + PostgreSQL,本地開發優先**。

> ⚠️ **localhost ≠ 部署環境**。本檔 `localhost:*` 範例僅供本地開發;部署規範見 `docs/Design-Base/06-Coolify-CD/`。

## Project Overview

<一句話描述專案。>

## Tech Stack

- **Frontend**:Next.js 16 (App Router) + TypeScript(`strict: true`)+ Redux Toolkit + RTK Query + Tailwind v4(Vite 為次選)
- **Backend**:Python + FastAPI + SQLAlchemy 2 async + Pydantic 2 + Alembic + uv + httpx + `pyjwt[crypto]` + `passlib[bcrypt]`
- **Database**:PostgreSQL(asyncpg)
- 版本鎖到 patch — 詳見 `docs/Design-Base/00-overview/01-versions.md`

## Agent Capabilities Baseline

本規範以「能讀檔 / 能寫檔 / 能執行 shell」為地板。
若工具更強(plan mode / sub-agent / hook / skill),只可**加強**遵守程度,**不可**降低:

- 有 hook → commit 格式檢查接 hook
- 有 sub-agent → `scan-project` / `reflect-rules` 可分派
- 都沒有 → 純照 `docs/Prompts/*.md` 步驟跑

不在地板能力清單的工具(如:純 chat 介面無 file write)→ 本規範不適用,需手動執行。

## Just-in-time Loading

依任務性質載入必要檔,**不預載**歷史報告(`fixed.md` / `reflect-report-*.md` / `scan-project/*`)。

> **完整任務 → 檔案 對照表 + 檔案 → 用途 索引**:`docs/Design-Base/README.md`(library API reference)。任何任務先讀本檔的「永遠載入」+ 該檔的對照表,即知要載哪些規範,**不必**全資料夾掃描。

### 永遠載入(任何任務)

- 本檔(`AGENTS.md`)
- `docs/Design-Base/README.md`(索引)
- `docs/Design-Base/00-overview/00-overview.md`(規範優先序 + 輸出語言)

### 依子任務載入(節錄;完整見 `docs/Design-Base/README.md`)

| 子任務 | 永遠載入 + 必讀 |
| --- | --- |
| **寫前端 UI/UX 純樣式 / 元件** | `02-frontend/00-overview.md`(風格地板) |
| 寫前端 data fetching | + `02-frontend/02-api-and-state.md` |
| 寫前端登入 / 認證 | + `02-frontend/03-env-and-auth.md` |
| 寫前端日期顯示 | + `02-frontend/04-datetime.md` |
| 寫前端 Dialog / 共用 Hook / 任何 reuse | + `02-frontend/05-components.md` |
| 寫前端 RWD / 樣式 / 版面 | + `02-frontend/06-rwd.md` |
| **寫後端新 API endpoint** | `03-backend/00-overview.md` + `03-backend/01-routing.md` |
| 寫保護 endpoint | + `03-backend/02-auth.md` |
| 寫 service 跨表 / hash | + `03-backend/03-async-and-tx.md` |
| 改後端啟動 / config | + `03-backend/04-config.md` + `00-overview/02-secrets.md` |
| 加 log / 處理錯誤 | + `03-backend/05-exceptions-and-logging.md` |
| 串第三方 | + `03-backend/06-clients.md` + `90-third-party-service/01-client-design.md` |
| 寫後端測試 | + `03-backend/07-testing.md` |
| 後端效能 / N+1 | + `03-backend/08-performance.md` |
| **設計新 DB 表** | `04-databases/00-overview.md` + `04-databases/01-identifiers.md` |
| 寫 Repository | + `04-databases/02-soft-delete.md` |
| 處理使用者資料 / PII | + `04-databases/03-passwords-and-pii.md` |
| 金額欄位 | + `04-databases/05-precision.md` |
| 時間欄位 | + `04-databases/06-timezone.md` + `00-overview/05-timezone.md` |
| 寫 migration | + `04-databases/08-alembic.md` |
| 優化 query | + `04-databases/09-indexes-and-perf.md` |
| **加套件** | `00-overview/01-versions.md` |
| 改 env / secret | `00-overview/02-secrets.md` + `00-overview/03-env-layers.md` |
| 改 CI workflow | `05-CI/00-overview.md` + 對應 job 檔 |
| 寫 / 改 Dockerfile / compose | `06-Coolify-CD/01-compose.md` + `02-dockerfile-*.md` |
| 串 SMTP / payment / 直連 Azure AD | `90-third-party-service/00-overview.md` + `01-client-design.md` + 對應服務檔 |
| 串公司 DF-SSO 中央登入器 | `90-third-party-service/08-df-sso.md`(實際落檔走 `sso-init` skill) |
| 發 PR / 收口 | `99-code-review/03-pr-self-check.md` + 對應 checklist |
| 寫 fixed.md / commit | `99-code-review/01-fixed-md.md` + `02-commit-message.md` |

> 上表所有路徑為 `docs/Design-Base/*` 子資料夾;Harness-Engineering 自身與採用方專案結構一致(`<project>/docs/Design-Base/`)。

## Build / Test / Lint

```bash
# Frontend
cd frontend && npm ci && npm run lint && npm run typecheck && npm run test && npm run build

# Backend
cd backend && uv sync --frozen && uv run ruff check . && uv run mypy . && uv run pytest && uv run alembic upgrade head
```

## Local Dev(僅 localhost)

```bash
# 前提:本機 PostgreSQL 已啟動,`.env` 已從 `.env.development.example` 複製並填空
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000   # backend
cd frontend && npm run dev                                                       # frontend(另一 terminal)
```

> 部署到 staging / production:見 `docs/Design-Base/06-Coolify-CD/`(Coolify + Docker Compose 規範)。

## Code Style

- **Output**:繁體中文(回應 / 註解 / 文件 / commit)
- **Comments**:不主動加;只在 *why* 非自明時加
- **TS**:`strict: true`、禁 `any`、props 用獨立 `interface`、函式必標型別
- **Python**:PEP 484/585 強制、禁 `Any` / `typing.List` / `typing.Dict`、用 `list[...]` / `dict[...]`、`AsyncSession` from `sqlalchemy.ext.asyncio`
- **Naming**:遵循各 area 的 `00-overview.md`(`02-frontend/00-overview.md` / `03-backend/00-overview.md` / `04-databases/00-overview.md`)

## Testing

- 後端整合測試**禁** mock SQL,須用真實測試 DB
- 第三方:`respx` / `httpx.MockTransport`
- 前端單元:`vitest`(Vite)/ `jest`(Next);e2e:Playwright

## Git Workflow

- Commit:`(AI?) <類型>: <描述>`(繁中);類型 `Add` / `Modify` / `Fix` / `Refactor` / `Docs`
- AI 產生**必**前綴 `(AI)`
- bug / 規範違反 → 同步 `fixed.md`(`docs/Design-Base/99-code-review/01-fixed-md.md`)
- `tasks-v*.md` checkbox 與頂部狀態必須一致
- PR self-check:`docs/Design-Base/99-code-review/03-pr-self-check.md`
- 未經明示授權,**禁**破壞性操作(`--force` / `reset --hard` / `--no-verify`)

## 毀滅性操作禁止

- **禁止任何 DROP 類資料庫操作**:不得執行、產生或建議 `DROP DATABASE` / `DROP SCHEMA` / `DROP TABLE` / `DROP COLUMN` 等會刪除資料或結構的 SQL / migration。
- **禁止刪除 Docker volume**:不得執行、產生或建議 `docker-compose down -v`、`docker compose down -v`、`--volumes` 等會移除 volume 的操作。
- **禁止使用 `rm -rf`**:不得在 shell、script、文件或自動化流程中使用 `rm -rf` 或等價的強制遞迴刪除操作。
- 任何可能造成資料遺失、不可逆清除、volume 消失、環境重建的指令,必須停下來改用安全替代方案,或請人類負責人手動確認與備份後處理。

## Security

- 機密**僅**透過 env var 注入;`.env` 必 gitignore;`git log --all -- .env` 須為空
- production 啟動 fail-fast(`Settings.model_validator`);機密**不可**入 log
- 偵測規則:`docs/Prompts/scan-project.md` `R-ENV-*` / `R-SEC-*` / `R-PII-*`

## Boundaries — 本模板不涵蓋

- **部署平台**:本模板限定 Coolify + Docker Compose(企業限定);非 Coolify 平台另尋 template
- **前端 / 後端之外的棧**(Vue / Spring / Go / MySQL...):用其他 template
- **業務模組**(auth / RBAC / dashboard):由各專案在 `docs/Tasks/v*/` 規劃,不預先 scaffold
- **Serverless**:僅 GCP / AWS,本模板不預設

## Rule Precedence

```
docs/Design-Base/* > docs/Arch/* > AGENTS.md / CLAUDE.md > docs/Tasks/*
```

衝突依此優先序機械式判定。`AGENTS.md` 與 `CLAUDE.md` 同層,內容須一致;`CLAUDE.md` 僅補充 Claude 特性,不重述。
