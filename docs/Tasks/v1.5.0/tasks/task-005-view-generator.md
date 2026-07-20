---
id: task-005
title: 語意化 view 產生器 — 各帳套 <schema>_en(A4)
status: pending
parallel: false
depends_on: [task-003]
affected_files:
  - backend/app/etl/view_generator.py
  - backend/tests/test_view_generator.py
estimated_hours: 3
---

## 目標

以同一份 confirmed mapping,迴圈各帳套 schema 在目標 RDS 產生語意化 view:`CREATE OR REPLACE VIEW <schema>_en.<english_table> AS SELECT <col> AS <english_name>, ... FROM <schema>.<table>`。schema 差異只在 view 層處理。

## 內容

- 新增 `backend/app/etl/view_generator.py`:
  - 輸入:目標 RDS 連線 + confirmed mapping(表層級決定 view 名、欄層級決定 SELECT alias;draft 一律不進 view)。
  - 迴圈目標 RDS 實際存在的帳套 schema(內省 information_schema;排除 `DS`/`erp_metadata`/`*_en` 自身),對「該 schema 實際存在且有 confirmed 表名」的表產 view;欄位取「表實際欄位 ∩ confirmed 欄位」,交集為空則跳過該表。
  - `CREATE SCHEMA IF NOT EXISTS <schema>_en` + `CREATE OR REPLACE VIEW`;**禁 DROP TABLE**(僅允許 `DROP VIEW`,限重建流程且註明);識別字全部經白名單驗證後引號化(`04-sql-safety.md`)。
  - 跨帳套共用主檔注意(propose A4):`GEM/GEN/ABM` 集中託管 G2203、M2201/S2202 為 synonym — 以「該 schema 實際存在的表」為準即自然涵蓋,不需特判。
  - 觸發時點:掛在 task-003 副本同步之後、**mapping 有異動才重生**(以副本重灌前後差異或 mapping 最大 `updated_at` 判斷);由 worker 呼叫,本 task 提供可獨立呼叫的函式與 worker 掛點(`app/worker/tasks.py` 的掛點由 task-003 預留一行呼叫,本 task 實作函式本體,不重複改動 tasks.py — 若需改動,與 task-003 worker 協調序列)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_view_generator.py` 全綠(含:confirmed 表產 view / draft 不產、欄位交集為空跳過、view SELECT alias=english_name、重跑冪等)
- [ ] `grep -n "DROP TABLE" app/etl/view_generator.py` 零命中
- [ ] ruff + mypy 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
