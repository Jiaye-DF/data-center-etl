# data-center-etl

<一句話描述專案。>

## 系統需求

- Python 3.14.1+
- Node 24.0.0+
- PostgreSQL 18+(請依官方文件本機安裝並啟動)

## 快速開始(本地開發)

### 一鍵啟動(推薦)

在 Claude Code 輸入 `/start-dev`,skill 會自動:
1. 確認當前是 scaffold 出來的專案目錄
2. 偵測 `:8000`(backend)、`:3000`(frontend)是否已被舊 process 占用 → kill
3. 各自啟動 uvicorn / vite dev server
4. 印出網址

停止:跑 `/stop-dev`,或重跑 `/start-dev`(會自動 kill 舊的)。

### 首次跑前要做的準備

1. **本機 PostgreSQL** 啟動,並依 `.env` 內 `DATABASE_URL` 的 user / password / db 建立 PG role 與 DB(預設 `data_center_etl`):
    ```sql
    -- ⚠ 密碼以本專案 .env 裡 DATABASE_URL 的 password 為準(.env 已 .gitignore)
    CREATE USER data_center_etl WITH PASSWORD '<把 .env DATABASE_URL 內的 password 貼這>';
    CREATE DATABASE data_center_etl OWNER data_center_etl;
    ```
2. `.env` 已由 `/init-project` 自動產出(內含 `DATABASE_URL`);若沒 `.env`(例如你選了「暫時跳過 PG 設定」),`cp .env.development.example .env` 並手動編輯
3. `cd backend && uv sync --frozen && uv run alembic upgrade head && cd ..`
4. `cd frontend && cp .env.local.example .env.local && npm ci && cd ..`
5. 跑 `/start-dev`(上一段)


### 驗證

- Backend Swagger:http://localhost:8000/api/docs
- Backend Health :http://localhost:8000/api/v1/health → `{data: {db: "ok"}}`
- Frontend       :http://localhost:3000

### 手動啟動(不用 skill)

若不在 Claude Code 環境,或要拆兩個 terminal 各自看 log:

```bash
# Terminal 1:後端
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2:前端
cd frontend && npm run dev
```

---

## 技術棧

- 前端:React 19.2.0 + TypeScript 5.9.3 + Vite 6.0.7 + Redux Toolkit + RTK Query + Tailwind v4
- 後端:FastAPI 0.136.1 + Pydantic 2 + uv + SQLAlchemy 2 (async) + Alembic
- 資料庫:PostgreSQL 18

## 工作流程

- 主分支 `main`,功能分支從 `main` 切出
- Commit message 繁體中文 `<類型>: <描述>`(類型:Add / Modify / Fix / Refactor / Docs)

## 部署

部署方案由本專案維護者依採用平台另行設計。本骨架為基本可跑的 React + FastAPI + PostgreSQL 環境。
