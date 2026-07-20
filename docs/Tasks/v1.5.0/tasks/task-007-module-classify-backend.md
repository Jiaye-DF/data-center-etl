---
id: task-007
title: B2 後端 — 快照加 GAT06 模組欄位 + datasets API 模組篩選
status: pending
parallel: false
depends_on: [task-003, task-004]
affected_files:
  - backend/alembic/versions/v150_add_module_code_to_rds_table_meta.py
  - backend/app/models/rds_table_meta.py
  - backend/app/services/snapshot_service.py
  - backend/app/api/v1/datasets.py
  - backend/app/schemas/dataset.py
  - backend/tests/test_snapshot_module_code.py
estimated_hours: 3
---

## 目標

資料表快照帶 ERP 模組代碼(`GAT_FILE.GAT06`),datasets 表清單 API 回傳模組並支援篩選 — 讓資料集頁可按模組分類。

## 內容

- alembic migration:`rds_table_meta` 加 `module_code`(text,nullable)。
- `snapshot_service.refresh`:內省時批量查 `DS.GAT_FILE` 的 `GAT06`(繁優先缺退簡,沿用/擴充 `dictionary.py` 既有批量查詢模式;字典缺 graceful null)→ 寫入快照。
- `api/v1/datasets.py` `list_tables`:回應加 `module_code`;新增 query 參數 `module`(等值篩選);`schemas/dataset.py` 對應更新。快照 Redis cache key 需納入 `module` 參數(沿用既有 cache fragment 模式)。
- **序列註記**:本 task 動 `datasets.py`(與 task-004 同檔)與 alembic head 鏈(task-003 之後)→ 已以 `depends_on` 序列化,禁與 003/004 並行。

## Acceptance

- [ ] `cd backend && uv run alembic upgrade head` → `downgrade -1` round-trip OK → 再 upgrade
- [ ] `uv run pytest tests/test_snapshot_module_code.py` 全綠(含:refresh 帶入 GAT06、字典缺為 null、`?module=` 篩選、cache key 區分)
- [ ] `uv run pytest` 既有全套件不紅
- [ ] ruff + mypy 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/08-alembic.md`
