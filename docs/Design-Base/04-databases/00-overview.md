# 04-databases — 資料庫入口 + 風格地板

鎖定 **PostgreSQL + asyncpg + SQLAlchemy 2 async + Alembic**。

> **永遠讀**:本檔為任何 DB 任務都必遵守的「風格地板」(必備欄位 / BaseModel / SQLAlchemy 風格 / 命名 / 禁物理刪除)。子任務專屬規則見對應子檔。

---

## 必備欄位(永遠遵守)

每張**業務資料表**必含:

| 角色 | 範例命名 | 型別 |
| --- | --- | --- |
| 內部主鍵 | `id` / `pid` / `ppid` | `BIGINT` 自增 |
| 對外識別碼 | `uid` / `<table>_uid` | `UUID` unique |
| 軟刪除 | `is_deleted` | `BOOLEAN` default `FALSE` |
| 建立時間 | `created_at` | `TIMESTAMP` |
| 更新時間 | `updated_at` | `TIMESTAMP` |
| 建立者 | `created_by` | `UUID` |
| 最後更新者 | `updated_by` | `UUID` |

`is_active` / `sort_order` **非全表必備**,需要時加。每欄必加 `COMMENT ON COLUMN` 中英雙語。

## SQLAlchemy Model(永遠遵守)

```python
class BaseModel(Base):
    __abstract__ = True
    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, unique=True, default=uuid4)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
    created_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    updated_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
```

- 所有 Model 繼承統一 `BaseModel`
- 用 SQLAlchemy 2 風格 `mapped_column`(**禁**舊 `Column(...)`)
- `is_active` / `sort_order` **不**放 `BaseModel`

## 軟刪除原則(永遠遵守)

- 業務資料**禁**物理刪除;設 `is_deleted = TRUE`
- SQLAlchemy 查詢**必**預設過濾 `is_deleted == False`
- 審計 / log 類表(append-only)不適用 — 請求 log(選用,需 Redis)見 `10-statistics-log.md`

詳細 Repository 命名規則見 `02-soft-delete.md`。

## 命名(永遠遵守)

- 索引:`idx_{table}_{column}`
- 唯一鍵:`uq_{table}_{column}`
- 外鍵:`fk_{table}_{ref}`
- Trigger:`trg_{table}_{action}`

---

## 子章節(依子任務載入)

- `01-identifiers.md` — pid 內部 / uid 對外 / 外部系統 ID
- `02-soft-delete.md` — Repository 命名強制
- `03-passwords-and-pii.md` — bcrypt + PII 隔離
- `04-sql-safety.md` — 禁字串拼接
- `05-precision.md` — 金額精度
- `06-timezone.md` — TIMESTAMP 與顯示層一致
- `07-connection.md` — 連線池
- `08-alembic.md` — migration 規範
- `09-indexes-and-perf.md` — 索引 + query 優化
- `10-statistics-log.md` — `<project>_statistics_log` 請求 log(**選用**,需 Redis;走共用套件)
