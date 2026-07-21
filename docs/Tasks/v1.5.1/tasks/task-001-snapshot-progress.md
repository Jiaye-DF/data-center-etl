---
id: task-001
title: 快照同步進度條(後端進度回報 + 前端進度條;補登)
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/etl/introspect.py
  - backend/app/services/snapshot_service.py
  - backend/app/api/v1/datasets.py
  - backend/app/schemas/rawdata.py
  - backend/tests/test_snapshot_refresh_progress.py
  - backend/tests/test_snapshot_module_code.py
  - frontend/src/lib/api/datasetApi.ts
  - frontend/src/components/datasets/DatasetBrowser.tsx
estimated_hours: 3
---

## 目標

快照同步(source / target)執行期間提供階段化進度:後端把「內省探測 / 字典查詢 / 寫入快照 / 維護排程」四階段進度寫 Redis 並開查詢端點,前端於同步期間輪詢顯示進度條。

> **補登註記**:本 task 於 propose 建立前先行實作完成(2026-07-21,分支 `dev-v1.5.1/snapshot-progress`,未 commit;程序疏失見 propose 決策記錄),此檔為補登。

## 內容(已實作)

- `introspect.snapshot_tables` 加 `on_progress` callback(row 探測每批 50 表回報一次)。
- `SnapshotService.refresh` 全程寫進度至 Redis key `datasets:{dataset}:refresh-progress`(TTL 600s 防漏清;結束含異常一律清 key);persist 階段每 200 表回報。
- 新端點 `GET /datasets/{dataset}/snapshot/refresh/progress`(admin;閒置回 `active=false`)。
- 前端 `DatasetBrowser` 於 `isRefreshing` 期間每 2 秒輪詢,顯示 `RefreshProgressBar`(階段名 + 已完成/總表數 + 百分比;總數未知顯示不定進度)。

## Acceptance

- [x] `cd backend && uv run pytest tests/test_snapshot_refresh_progress.py` 全綠(refresh 寫入各階段 / 結束清 key / 端點閒置 inactive / 進行中回進度 / member 403)
- [x] 後端 `ruff check` + `mypy app` 無新增錯誤(既有 `schedule_repo.py:528` mypy 錯誤與本 task 無關)
- [x] 前端 `npm run typecheck` + `npm run lint` 全綠
- [x] 完整後端套件 `uv run pytest tests -q` 全綠(299 passed,2026-07-21)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
