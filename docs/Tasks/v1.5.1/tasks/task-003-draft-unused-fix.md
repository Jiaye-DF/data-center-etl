---
id: task-003
title: 英文草稿 unused 命名修正 + 重新 seed
status: done
parallel: true
depends_on: []
affected_files:
  - docs/ERP-Analyze/data/semantic_draft.tsv
estimated_hours: 2
---

## 目標

修正英文草稿命名缺陷(user 明示):中文名為「No Use」(不分大小寫)或空值的欄位,英文名一律採**原始欄名小寫**(例 `APS59` → `aps59`),不得為 `unused_*` 等失真名稱;修正後重新 seed 至 RDS(draft 更新、confirmed 不覆寫)。

## 內容

- 轉換規則(對 `semantic_draft.tsv` 全量套用,一次性轉換,不新增常駐腳本):
  - `ZH_NAME` 為 `No Use` / `no use` / 空字串 → `EN_NAME = COLUMN_NAME 小寫`。
  - 其餘列不動;表層級列(`COLUMN_NAME` 空)不適用本規則。
- 轉換後以既有 `backend/scripts/seed_semantic_mappings.py` 重新 seed(目標 RDS;需 `AWS_RDS_*` env):draft 列更新、confirmed 列略過(腳本既有保護)。
- 驗證 BMA_FILE(已 confirmed 樣本表)未被覆寫。

## Acceptance

- [x] `grep -c "unused" docs/ERP-Analyze/data/semantic_draft.tsv` = 0(修正前 287 筆 unused 前綴;實際改寫 290 筆含空中文名列)
- [x] TSV 總列數不變(12,280 列,僅改 EN_NAME 欄)
- [x] seed 輸出「新增 0 / 更新 12246 / 略過(已複核)34」,結束碼 0(2026-07-21,目標 RDS erp_etl_hub_test)
- [x] 重跑一次 seed,統計相同(冪等);RDS 查證:`english_name LIKE 'unused%'` 0 筆、BMA_FILE 34 筆 confirmed 未被覆寫

## 執行註記

- 例外 1 筆:`FAT_FILE.FAT12` 中文名「NO USE 原因碼」為**真語意欄位**(停用原因碼),非佔位 No Use,不適用「改回欄名」規則;草稿英文名由 `unused_reason_code` 改為 `no_use_reason_code`(貼中文語意、避免與佔位混淆),仍為 draft 待複核。

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
