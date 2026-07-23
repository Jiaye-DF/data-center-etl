---
id: task-001
title: 同步 schema drift 偵測 + 目標表自動 ADD COLUMN
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/etl/mirror.py
  - backend/tests/test_mirror.py
estimated_hours: 3
---

## 目標

來源表新增欄位後,鏡像同步不再整表失敗:`write_mirror` 既有表路徑在 TRUNCATE 前比對來源欄位 vs 目標實體欄位,缺欄自動 `ALTER TABLE ... ADD COLUMN`(只加不刪),讓後續 INSERT 欄位清單完整命中。

## 內容

- 掛點:`backend/app/etl/mirror.py` `write_mirror` 的「表已存在」分支(現行僅 TRUNCATE)。以 `information_schema.columns` 查目標表實體欄位(bind params),與傳入 `columns: Sequence[MirrorColumn]` 比對;來源有、目標無 → 逐欄 `ALTER TABLE <schema>.<table> ADD COLUMN <name> <type_sql>`(識別字一律 `quote_ident`,型別片段沿用 `MirrorColumn.type_sql` 既有重建規則,含時間型別 naive timestamp 決議)。
- **只加不刪**:目標有、來源無的欄位一律不動(INSERT 欄位清單本來就只列來源欄,殘欄補 NULL 無害);禁任何 DROP / ALTER TYPE / RENAME。
- ALTER 與 TRUNCATE / INSERT 同在單表交易內:中途失敗整批 rollback,維持既有「單表失敗不中斷整輪」語意;不得出現半補欄位。
- 無 drift 時(欄位集合一致)不得多出 ALTER 往返,僅增加一次 information_schema 查詢;`writer.py`(config-ETL 已下線路徑)不動。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_mirror.py` 全綠,含新測試:(a) 既有表 + 來源多一欄 → 目標表出現該欄且該欄資料寫入;(b) 目標多殘欄 → 不動、INSERT 正常;(c) 無 drift → 無 ALTER 語句
- [ ] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤
- [ ] `grep -n "ADD COLUMN" backend/app/etl/mirror.py` 有實作;`grep -nE "DROP (COLUMN|TABLE)" backend/app/etl/mirror.py` 無新增命中

## 必讀檔(Just-in-time)

- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/04-databases/06-timezone.md`
- `docs/Design-Base/00-overview/05-timezone.md`
- `docs/Design-Base/03-backend/07-testing.md`

## 派工建議

- model:opus / effort:high(核心 ETL 寫入路徑,錯誤代價高)
