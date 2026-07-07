---
id: task-006
title: 移除後端「排程涵蓋」+ config-ETL 端點/service/repo + api/v1/__init__ 收斂
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/api/v1/__init__.py
  - backend/app/api/v1/etl_tables.py
  - backend/app/api/v1/schedule_coverage.py
  - backend/app/services/etl_config_service.py
  - backend/app/services/schedule_coverage_service.py
  - backend/app/repositories/etl_config_repo.py
  - backend/app/repositories/schedule_coverage_repo.py
  - backend/app/schemas/schedule_coverage.py
  - backend/tests/test_etl_config_api.py
  - backend/tests/test_schedule_coverage_api.py
estimated_hours: 2
---

## 目標

程式面下線 v1.3.0 的「排程涵蓋」後端與 v1.1 config-ETL 的 API/service/repo 層:刪除對應檔案並在 `api/v1/__init__.py` 移除其 router 掛載。**不碰** worker/engine（歸 005）、`schedule_service.py`/`runs.py`（歸 004）、model 與 DB(禁 DROP;`etl_tables`/`etl_mappings` model 保留,列 009 人工清單)。

## 內容

- 刪除檔案:`api/v1/etl_tables.py`、`api/v1/schedule_coverage.py`、`services/etl_config_service.py`、`services/schedule_coverage_service.py`、`repositories/etl_config_repo.py`、`repositories/schedule_coverage_repo.py`、`schemas/schedule_coverage.py`、`tests/test_etl_config_api.py`、`tests/test_schedule_coverage_api.py`。
- `api/v1/__init__.py`:移除 `etl_tables`、`schedule_coverage` 的 import 與 `include_router`;**保留** health/auth/sso/datasets/schedules/runs/audit_logs/sync。
- 確認無殘留 import:全 repo `grep` 這些模組零引用（若 004/005 尚未完成致 `schedule_service`/`worker` 仍 import 已刪模組,屬跨 task 收口——本 task 只負責自己刪的檔與 `__init__`,其 Acceptance 以「本 task 影響檔 + __init__ 可 import」為準;全套件綠由收口驗)。

## Acceptance

- [ ] 上述 9 檔已刪除(`[ ! -f backend/app/api/v1/etl_tables.py ]` 等,或 `git status` 顯示 deleted)
- [ ] `cd backend && python -c "import app.api.v1"` 成功（`__init__.py` 無殘留 import 已刪模組）
- [ ] `cd backend && uv run ruff check app/api/v1/__init__.py` 全綠
- [ ] `grep -rn "etl_config_service\|schedule_coverage\|etl_config_repo\|EtlConfigService" app/api app/services app/repositories app/schemas` 無命中（本 task 範圍內零引用）
- [ ] `api/v1/__init__.py` 仍含 `schedules` 與 `runs` 的 include_router（未誤刪）

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
