---
id: task-002
title: 語意映射自動補列模組(confirmed + 表層級 + 別名查重 + DS 字典 zh)
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/etl/semantic_autofill.py
  - backend/tests/test_semantic_autofill.py
estimated_hours: 4
---

## 目標

新模組 `semantic_autofill`:比對目標 RDS 帳套 schema 實體欄位 vs `erp_metadata.semantic_mappings` 既有列,缺列自動補 `status='confirmed'`,讓新欄位(與缺表層級列的表)能進 view 與 JSON 查詢。純模組 + 測試,本 task 不掛同步流程(掛接為 task-003)。

## 內容

- 內省目標 RDS 帳套 schema / 表 / 欄位:沿用 `view_generator.py` 的 `information_schema` 查詢與 schema 排除慣例(排 DS / erp_metadata / `*_view` / `*_en`);mapping 現況一次撈全量(`SELECT table_name, column_name FROM erp_metadata.semantic_mappings`),記憶體比對,禁逐欄查詢 N+1。
- 補列規則(**既有列不論 draft / confirmed 一律不覆寫**):
  - 欄層級缺列 → insert `(table_name, column_name, english_name=原始欄名小寫, zh_name=DS 字典中文名或空, status='confirmed', updated_by=全零 UUID)`;`zh_name` 重用 `app/etl/dictionary.py` `fetch_column_comments`(來源連線取字典),取不到留空。
  - 表層級列(`column_name=''`)缺 → 一併補,`english_name=原始表名小寫`。
- 別名查重(同表內):自動英文名撞同表既有 `english_name`(含本輪擬插入者)→ 確定性規避:改用 `<欄名小寫>_col`,仍撞則附遞增序號 `_col2`、`_col3`…;不得讓 view 因 SELECT 別名重複建不起來。
- 冪等 / 併發安全:寫入用 `INSERT ... ON CONFLICT (table_name, column_name) DO NOTHING`(值一律 bind params,識別字白名單常值);多 worker 同時執行不得炸 PK。
- 回傳統計 dataclass(補欄列數 / 補表層級數 / 撞名規避數),供掛接端 log。`updated_at` 為 naive timestamp(UTC+8,DEFAULT 已處理,不另傳)。

## Acceptance

- [x] `cd backend && uv run pytest tests/test_semantic_autofill.py` 全綠,含:(a) 缺欄列補 confirmed(english=小寫原欄名 / updated_by=全零);(b) 既有 draft 與 confirmed 列不覆寫;(c) 表層級缺列補表名小寫;(d) 撞名走 `_col` / 序號規避;(e) ON CONFLICT 重跑冪等;(f) zh_name 取字典值、缺則空 — 12 passed
- [x] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤(schedule_repo.py:528 rowcount 為既有未觸碰檔錯誤,非本 task 新增)
- [x] `grep -n "ON CONFLICT" backend/app/etl/semantic_autofill.py` 有命中;模組無任何 UPDATE / DELETE 語句(`grep -nE "UPDATE|DELETE" backend/app/etl/semantic_autofill.py` 無命中)

## 必讀檔(Just-in-time)

- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/01-identifiers.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/00-overview/05-timezone.md`
- `docs/Design-Base/03-backend/07-testing.md`

## 派工建議

- model:opus / effort:high(規則分支多:不覆寫 / 表層級 / 撞名 / 冪等)
