# 09-indexes-and-perf — 索引 + Query 優化

> **何時讀**:優化 query / N+1 排查時讀。

## 索引

- 外鍵欄位**必**索引
- where / order by 高頻欄位**必**索引
- 軟刪除過濾可用 partial index(`WHERE is_deleted = FALSE`)
- 命名:`idx_{table}_{column}` / `uq_{table}_{column}` / `fk_{table}_{ref}` / `trg_{table}_{action}`

## Query 優化(N+1 / EXPLAIN)

- ORM 列表查詢**必**用 `selectinload(...)` / `joinedload(...)` 預載 relationship,**禁**單純 `relationship lazy load`
- DB query plan(`EXPLAIN ANALYZE`)抽查所有 list endpoint
- 測試環境啟用 `echo=True` / SQL log,觀察 query 數
