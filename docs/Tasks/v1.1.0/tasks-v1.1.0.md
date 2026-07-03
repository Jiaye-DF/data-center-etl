# Tasks v1.1.0

> 狀態:未開始(已完成 0/12)
> 變更:2026-07-03 移除 task-013(Coolify 部署收口)— 部署與 AWS/EC2 建立由 user 人工執行(見 propose 變更紀錄);系統面交付止於 task-012。
> 來源:`propose-v1.1.0.md`(scope 地板,禁動)
> 範圍:ETL 管理後台(既有 `backend/` `frontend/` 骨架上開發)+ taskiq/redis 排程 + 容器內 ETL 執行 + Coolify 部署。taskiq / redis 不在鎖定技術棧,經 user 明示採用(propose 已註記)。v1.0.0 `etl/`(Glue 版)**凍結**:僅唯讀參考,任何 task 不得修改。
> 執行環境註記:各 task Acceptance 指令為 bash 語法;本機為 Windows,worker 一律以 **Git Bash** 執行驗證指令。

## 清單

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | 自有 DB schema(models + migration)+ 後端依賴鎖版 | done(worker: claude-A) | ✓ | — | `backend/app/models/*`(6 新檔)/ `backend/alembic/versions/xxxx_add_v110_core_tables.py` / `backend/pyproject.toml` / `backend/uv.lock` / `backend/tests/test_models_v110.py`(全 11 檔見 task 檔) |
| 002 | 本地帳密登入 + init_admin(env)+ 角色權限 | done(worker: claude-A) | ✓ | 001 | `backend/app/api/v1/auth.py` / `api/v1/__init__.py` / `schemas/auth.py` / `services/auth_service.py` / `repositories/user_repo.py` / `core/config.py` / `core/security.py` / `api/deps.py` / `main.py` / `tests/test_auth.py` |
| 003 | DF-SSO 後端整合(雙軌之 SSO 側) | done(worker: claude-A) | ✗ | 002 | `backend/app/api/v1/sso.py` / `api/v1/__init__.py` / `clients/df_sso.py` / `services/sso_service.py` / `core/config.py` / `tests/test_sso.py` |
| 004 | ETL 設定管理 API(表清單/啟停/mapping/Comment) | pending | ✗ | 001,003 | `backend/app/api/v1/etl_tables.py` / `api/v1/__init__.py` / `schemas/etl_config.py` / `services/etl_config_service.py` / `repositories/etl_config_repo.py` / `tests/test_etl_config_api.py` |
| 005 | 排程 / 執行紀錄與詳細 log / 手動觸發 API | pending | ✗ | 004,007 | `backend/app/api/v1/schedules.py` / `api/v1/runs.py` / `api/v1/__init__.py` / `schemas/schedule.py` / `schemas/run.py` / `services/schedule_service.py` / `repositories/schedule_repo.py` / `repositories/run_repo.py` / `tests/test_schedule_api.py` / `tests/test_runs_api.py` |
| 006 | ETL 執行核心(純 Python,DB 設定驅動 + 逐表詳細 log) | done(worker: claude-B) | ✓ | 001 | `backend/app/etl/`(engine/reader/writer/comments/transforms)/ `tests/test_etl_engine.py` / `tests/test_etl_transforms.py` |
| 007 | taskiq + redis 排程服務(broker/worker/scheduler) | done(worker: claude-B) | ✓ | 006 | `backend/app/worker/`(broker/tasks/scheduler)/ `tests/test_worker.py` |
| 008 | v1.0.0 mapping 設定匯入自有 DB(seed) | done(worker: claude-C) | ✓ | 001 | `backend/scripts/seed_etl_config.py` / `tests/test_seed_etl_config.py` |
| 009 | 前端登入頁(雙軌)+ 後台佈局殼 + auth guard | pending | ✓ | 002,003 | `frontend/src/app/login/page.tsx` / `middleware.ts` / `app/(main)/layout.tsx` / `app/(main)/page.tsx` / `lib/api/authApi.ts` / `lib/auth/useAuth.ts` / `app/error.tsx` / `app/global-error.tsx` |
| 010 | 前端 Data Table 管理頁(清單/啟停/mapping/Comment) | pending | ✓ | 004,009 | `frontend/src/app/(main)/tables/*` / `lib/api/etlConfigApi.ts` / `components/tables/*` |
| 011 | 前端排程管理 + 執行紀錄/逐表詳細 log 頁 | pending | ✓ | 005,009 | `frontend/src/app/(main)/schedules/*` / `app/(main)/runs/*` / `lib/api/scheduleApi.ts` / `lib/api/runApi.ts` / `components/runs/RunLogTable.tsx` |
| 012 | Docker 化(etl_ prefix image + redis/worker/scheduler) | pending | ✓ | 007 | `docker-compose.yml` / `backend/Dockerfile` / `.env.example` |

## 拆解摘要

- **總數**:12 個 task,預估 ~41 hr;後端 8、前端 3、部署 1(Coolify 實際部署由 user 人工執行,不在 task 內)
- **起手可認領(無依賴)**:task-001
- **依賴鏈**:
  - 後端 API:`001 → 002 → 003 → 004 → 005`(003–005 共用 `api/v1/__init__.py`,**序列化**,故標 ✗)
  - ETL 執行:`001 → 006 → 007`(與 API 鏈**可並行**)
  - seed:`001 → 008`(可並行)
  - 前端:`(002,003) → 009 → (010 ∥ 011)`(010/011 檔案不重疊可並行,但分別等 004/005)
  - 收口:全 task done 後由 **user 人工**執行 Coolify / AWS 部署與正式環境驗收
- **阻塞點**:001 全域前置;`api/v1/__init__.py` 使後端 API 鏈序列化;005 需等 007(手動觸發 enqueue)
- **關鍵設計約束(避免同檔互鎖)**:
  1. **依賴鎖版集中 task-001**:`pyproject.toml` / `uv.lock` 只有 001 動,其餘 task 一律不改
  2. **`api/v1/__init__.py` 匯集模式由 002 建立**,003/004/005 依賴鏈序列化後各自掛 router
  3. **`(main)/layout.tsx` 只屬 009**(nav 三項一次建好),010/011 各自新增 route 目錄不回頭改 layout
  4. **v1.0.0 `etl/` 凍結**:006/008 唯讀參考 mapping 與轉換行為,禁修改
- **豁免註記**:taskiq / redis 經 user 授權採用;正式化規範候選走 `/reflect-rules`

## Scope ↔ Task 對照(propose In Scope 逐條)

| propose In Scope 條目 | 對應 task |
| --- | --- |
| 管理後台 backend(設定/排程/觸發/紀錄/權限 API) | 002,004,005 |
| 管理後台 frontend(表為中心 UI) | 009,010,011 |
| 自有 DB(權限/設定/排程/紀錄,source of truth) | 001,008 |
| 詳細執行 Log(逐表,含 stack trace) | 001(表結構),006(寫入),005(查詢 API),011(UI) |
| 排程服務(taskiq + redis) | 007,012 |
| ETL 容器內執行(不依賴 Glue) | 006 |
| 登入與權限(雙軌 + init_admin env) | 002,003,009 |
| Docker 化(etl_ prefix) | 012 |
| 可部署產物(image + env 範本;部署本身 user 人工) | 012 |

## 驗收標準覆蓋(propose 驗收逐條)

| propose 驗收標準 | 覆蓋 task | 屬性 |
| --- | --- | --- |
| compose up 全服務 healthy | 012 | 本地可驗 |
| image 全 `etl_` prefix | 012 | 本地可驗 |
| 排程到點自動執行 + 紀錄 | 007(機制;本地 compose 可實測) | 正式環境由 user 部署後自驗 |
| 手動觸發成功 + Comment 非空 | 005,006(機制 + 測試;本地可實測) | 正式環境由 user 自驗 |
| 逐表詳細 log(含失敗 stack trace) | 006(單元測試)/ 011(UI) | 本地可驗 |
| 停用表不處理且 log 可證 | 004,006(測試) | 本地可驗 |
| viewer 寫入 403 | 002,004,005(測試) | 本地可驗 |
| init_admin env 登入 + 缺 env fail-fast | 002(測試) | 本地可驗 |
| DF-SSO 登入完成 | 003,009 | 需 DF-SSO 可達,可本地驗 |
| Coolify 部署 + EC2 寫入 RDS | —(user 人工,不拆 task) | user 自驗 |
| v1.0.0 `etl/` 無異動 | 全 task 約束(各 task Acceptance) | 本地可驗 |
