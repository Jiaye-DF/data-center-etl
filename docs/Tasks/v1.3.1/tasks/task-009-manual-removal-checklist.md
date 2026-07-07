---
id: task-009
title: 人工移除清單文件(待 DROP 的表 / 欄 + 備份指引)
status: pending
parallel: true
depends_on: []
affected_files:
  - docs/Tasks/v1.3.1/manual-removal-checklist.md
estimated_hours: 1
---

## 目標

產出「人工移除清單」文件:列出本版「程式面下線但實體保留」的資料表 / 欄位,供人類負責人**備份後手動 DROP**(CLAUDE.md 禁 repo 產生 DROP migration)。

## 內容

`docs/Tasks/v1.3.1/manual-removal-checklist.md` 至少含:
- **待移除對象**(逐項:物件 / 型別 / 下線於哪個 task / 程式面是否已零引用):
  - `etl_tables`(表,v1.1 config ETL)
  - `etl_mappings`(表,v1.1 config ETL)
  - `schedules.etl_table_pid`(欄,deprecated)
  - `rds_table_meta.sync_excluded`(欄,v1.3.0 逐表排除,已廢止)
- **每項前置檢查**:程式面零引用確認指令(如 `grep -rn "etl_table_pid" backend/app` 應無命中,`sync_excluded` 同)。
- **備份指引**:DROP 前 `pg_dump` 該表 / 全庫的建議指令(佔位,實際連線由負責人填);列明「先備份、確認無引用、再於維護窗口手動執行」。
- **明確聲明**:本 repo 不提供 DROP migration;實體 DROP 為人工、不可逆,由負責人執行並記錄。
- 標注相依:`etl_tables`/`etl_mappings` 若被 `schedules.etl_table_pid` FK 參照,DROP 順序需先解 FK(說明,不代執行)。

## Acceptance

- [ ] `[ -f docs/Tasks/v1.3.1/manual-removal-checklist.md ]` 為真
- [ ] 文件含上列 4 個待移除對象,每項有「下線 task」「零引用檢查指令」「備份指引」三欄/段
- [ ] 文件明寫「repo 不產生 DROP migration,實體移除由人工執行」
- [ ] `grep -iE "DROP TABLE|DROP COLUMN" docs/Tasks/v1.3.1/manual-removal-checklist.md` 若出現,僅作為「人工待執行指令範例」且明標為手動(非 repo 自動化)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/08-alembic.md`
