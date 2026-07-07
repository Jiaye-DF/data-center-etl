---
id: task-003
title: 快照同步自動建排程 + 收斂(每表 upsert / 缺表軟刪 / 軟刪 v1.3.0 全表舊排程)
status: pending
parallel: true
depends_on: [task-002]
affected_files:
  - backend/app/services/snapshot_service.py
  - backend/tests/test_snapshot_autoschedule_v131.py
estimated_hours: 3
---

## 目標

在 `SnapshotService.refresh`(dataset=source)完成 metadata upsert 後,自動為每張來源表維護一筆專屬排程:無排程者新增(預設每天 00:00、停用)、來源表消失者軟刪、v1.3.0 遺留全表排程一次性軟刪。此即「既有資料收斂 + 新表自動納入」的落地(backfill 由下次 refresh 自然補齊)。

## 內容

- 先 Read `services/snapshot_service.py` 確認 refresh(source)的交易邊界與 upsert 流程、`db_now`、`SYSTEM_ACTOR_UID`(或系統帳號來源)。
- refresh(dataset=source)metadata upsert 完成後,於**同交易或緊接**執行:
  1. 對本輪偵測到的每張來源表 `ScheduleRepository.upsert_for_source_table(schema, table, name=f"{schema}.{table}", cron_expr="0 0 * * *", is_enabled=False, actor_uid=...)`(既有排程不覆蓋啟停/cron)。
  2. `soft_delete_by_source_tables_absent(present=本輪表集合, actor_uid=...)`(來源表消失 → 對應排程軟刪)。
  3. `soft_delete_legacy_all_table(actor_uid=...)`(僅需生效一次,冪等:已無 source_schema IS NULL 者回 0)。
- 冪等 / 可重入:失敗時下次 refresh 補齊(不得留「表有快照、無排程」中間態——與 metadata upsert 同交易提交)。
- **僅 dataset=source** 觸發自動建排程(target 不建)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_snapshot_autoschedule_v131.py -q` 全綠(測試 DB localhost:5435;以 fake / monkeypatch 免連 RDS,對齊既有 `tests/test_snapshot_service.py`)
- [ ] `cd backend && uv run ruff check app/services/snapshot_service.py tests/test_snapshot_autoschedule_v131.py` 全綠
- [ ] 測試涵蓋:refresh(source)後每張來源表各有一筆 `cron_expr="0 0 * * *"`、`is_enabled=false` 排程;既有已啟用排程再 refresh 不被重置為停用;來源表移除後該排程 `is_deleted=true`;預先塞一筆 `source_schema IS NULL` 的 v1.3.0 排程 → refresh 後被軟刪
- [ ] refresh(dataset=target)不建立任何排程

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/00-overview/05-timezone.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
