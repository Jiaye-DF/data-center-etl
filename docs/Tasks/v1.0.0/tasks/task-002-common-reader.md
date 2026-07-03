---
id: task-002
title: common/reader — 來源讀取(erp_migration_test:DS/M2201)
status: done
parallel: true
depends_on: [task-001]
affected_files:
  - etl/common/reader.py
  - etl/tests/test_reader.py
estimated_hours: 2
---

## 目標

實作 `common/reader.py`:以 Spark JDBC 從來源 RDS PostgreSQL `erp_migration_test` DB 讀取指定 schema(`DS` / `M2201`)的表格為 DataFrame,連線資訊由 env / config 注入。

## 範圍要點

- 提供 `read_table(spark, schema, table)`(或等價 API)回傳 Spark DataFrame。
- JDBC URL / user / password 一律從 env 取(對齊 `00-overview/02-secrets.md`),**禁**硬編。
- schema / table 名稱組裝需防注入:白名單 / 識別字引號處理,不做字串直接拼進 SQL(對齊 `04-databases/04-sql-safety.md`)。
- 不含轉換邏輯(轉換屬 004/005);reader 只負責讀取。

## Acceptance

- [ ] `python -m py_compile etl/common/reader.py` 通過(exit 0)
- [ ] `cd etl && python -m pytest tests/test_reader.py -q` 全綠(對「識別字組裝 / JDBC URL 由 env 組成」等純函式做單元測試,不需真連 DB)
- [ ] `python -c "import etl.common.reader as r; print(hasattr(r,'read_table'))"` 印 `True`
- [ ] `! grep -nE "password\\s*=\\s*['\"]" etl/common/reader.py`(無硬編密碼)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/02-secrets.md`(連線憑證以 env 注入)
- `docs/Design-Base/04-databases/00-overview.md`(DB 風格地板)
- `docs/Design-Base/04-databases/04-sql-safety.md`(禁字串拼接、識別字安全)
- `docs/Design-Base/04-databases/07-connection.md`(連線設定)
