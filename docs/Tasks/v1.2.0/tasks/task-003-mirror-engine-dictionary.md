---
id: task-003
title: 自動鏡像 + DS 字典 COMMENT 轉換引擎(保留型別/comment 放寬)
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/etl/mirror.py
  - backend/app/etl/dictionary.py
  - backend/tests/test_mirror.py
  - backend/tests/test_dictionary.py
estimated_hours: 4
---

## 目標

新增自動鏡像引擎:內省來源表真實型別 → 目標端保留型別 `CREATE SCHEMA/TABLE IF NOT EXISTS` + `TRUNCATE` + 分批 `INSERT` → 套 DS 字典中文 COMMENT。獨立於既有 config-driven 引擎(不動 `engine/reader/writer/comments.py`,唯讀重用 `reader.rds_database_url`)。

## 設計要點

- `etl/dictionary.py`:DS 字典查詢(對 source RDS)。
  - 表中文名:`SELECT "GAT03" FROM "DS"."GAT_FILE" WHERE lower("GAT01")=:t AND "GAT02"=:lang`(繁 `'0'` 優先,缺 → `'2'`)。
  - 欄中文名:`SELECT lower("GAQ01") k, "GAQ03" v FROM "DS"."GAQ_FILE" WHERE lower("GAQ01") = ANY(:cols) AND "GAQ02"=:lang`(一次批量查該表所有欄;繁優先缺退简)。
  - 識別字白名單引號化、值走 bind params(`04-sql-safety.md`);字典表缺失時 graceful 回空(不 raise)。
- `etl/mirror.py`:
  - `list_source_tables()`:列所有非系統 schema 的 base table;**DS schema 排最前**(字典先落地),其餘依名。
  - `mirror_table(schema, table)`:
    1. 內省來源欄位 + **真實型別**(含 varchar 長度 / numeric precision,scale;組正確 DDL)。
    2. 目標:`CREATE SCHEMA IF NOT EXISTS` → 表不存在 `CREATE TABLE`(原型別)/ 存在 `TRUNCATE`(**禁 DROP**)→ 以 server-side cursor 分批讀來源、分批 INSERT(禁整表物化,對齊 scan AD-006)。
    3. COMMENT:查字典組 `COMMENT ON TABLE` / `COMMENT ON COLUMN`;**無對應者略過該欄 COMMENT(不 raise)** —— comment 放寬(In Scope ⑦)。
    4. 回傳寫入筆數。
  - 連線重用 `reader.rds_database_url(SOURCE/TARGET env)`;機密不 log。
  - 型別對映以來源 `information_schema.columns` 的 data_type + 長度/精度重建;未知型別保守落 TEXT 並記 log。

## Acceptance

- [ ] `uv run pytest tests/test_dictionary.py` 全綠(fake/真連:GAT/GAQ 繁優先缺退简;字典缺失回空不 raise)
- [ ] `uv run pytest tests/test_mirror.py` 全綠(以 fake reader/writer 或測 DB:DS 排序最前;無 comment 欄不 raise;TRUNCATE 重灌不 DROP;分批不整表物化)
- [ ] 小規模真跑(worker 或 script,單一小表如 `DS.AAA_FILE`):目標 `erp_etl_hub_test` 出現 `DS.AAA_FILE`,型別與來源一致,`COMMENT ON TABLE` = 「帳別參數檔」、`AAA01` COMMENT = 「帳別編號」(以 psql `\d+` 或 `col_description` 驗)
- [ ] `uv run ruff check . && uv run mypy app` green
- [ ] 既有引擎未動:`git diff --stat` 不含 `app/etl/{engine,reader,writer,comments}.py` 修改

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/08-performance.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/04-databases/07-connection.md`
- `docs/Design-Base/00-overview/02-secrets.md`
