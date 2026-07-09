---
id: task-003
title: RBAC 後端 — 資料層端點全面 require_admin
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/api/v1/datasets.py
  - backend/app/api/v1/schedules.py
  - backend/app/api/v1/runs.py
  - backend/app/api/v1/sync.py
  - backend/app/api/v1/dashboard.py
  - backend/app/api/v1/audit_logs.py
  - backend/tests/test_sync_api.py
  - backend/tests/test_runs_api.py
  - backend/tests/test_schedule_api_v131.py
  - backend/tests/test_snapshot_service.py
  - backend/tests/test_audit_log.py
estimated_hours: 3
model: sonnet
effort: medium
---

## 目標

ETL 後台 API **讀寫全部** admin-only:datasets / schedules / runs / sync / dashboard / audit_logs 六個 router 的所有端點,非 admin 一律 403。auth(login/logout/me)、sso、health 不變。

## 實作要點

1. 六個 router 檔把 `require_login` 依賴全數換成 `require_admin`(`app/api/deps.py:106` 既有,勿新增機制);寫入類端點原本已是 `require_admin` 者不動。
2. **禁**動 `deps.py` / auth / sso / health;**禁**改回應殼與路由路徑(僅權限依賴變更)。
3. 既有測試更新:原斷言「viewer 可讀(200)」的案例改斷言 403;各檔至少一條「viewer GET → 403」與「admin 不變(200)」對照;未登入仍 401(語意:401=未登入、403=已登入無權,不可混)。
4. 本任務為權限收緊(propose 已註記 user 裁定走 minor);commit message 註明影響:非 admin 既有可讀行為移除。

## Acceptance

- [x] `uv run pytest` 全綠(含更新後的五個測試檔)
- [x] `grep -rn "require_login" backend/app/api/v1/{datasets,schedules,runs,sync,dashboard,audit_logs}.py` 無輸出(全面換畢)
- [x] `uv run ruff check .` 通過;`uv run mypy .` 無新增錯誤
- [ ] `docker compose up -d --build backend` 後手測:viewer 帳號 token `curl /api/v1/datasets/source/schemas` 回 403;admin 回 200;未帶 token 回 401(**待 orchestrator 手測**)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/07-testing.md`
