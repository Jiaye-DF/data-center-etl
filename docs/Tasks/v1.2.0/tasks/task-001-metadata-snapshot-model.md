---
id: task-001
title: metadata 快照資料模型 + migration + 依賴鎖版(redis)
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/models/rds_table_meta.py
  - backend/app/models/__init__.py
  - backend/alembic/versions/v2_add_rds_table_meta.py
  - backend/pyproject.toml
  - backend/uv.lock
  - backend/tests/test_models_v120.py
estimated_hours: 2
---

## 目標

建立 RDS 結構 metadata 快照表 `rds_table_meta`(每筆代表 dataset+schema+table 的 metadata 與同步狀態),供瀏覽頁改讀快照、同步鏈記錄狀態;並集中本版依賴鎖版(新增 `redis` 直用 client)。

## 設計要點

- 表 `rds_table_meta` 欄位(除 BaseModel 必備 pid/uid/is_deleted/created_at/updated_at/created_by/updated_by 外):
  - `dataset`:StrEnum(`source` / `target`)
  - `schema_name` / `table_name`:varchar
  - `column_count`:int
  - `row_count`:int(bounded,> 1000 存 1001)
  - `snapshot_at`:timestamp(此筆 metadata 擷取時間,可空)
  - `last_synced_at`:timestamp(可空,最近從 RDS 同步到 hub 的時間)
  - `last_transformed_at`:timestamp(可空,最近套字典 COMMENT 的時間)
- 唯一鍵:`(dataset, schema_name, table_name)` 於未刪除範圍(供 upsert)。
- 依 `04-databases` 命名 / 軟刪除 / 時區規範;時間欄型別對齊既有 v1.1 表。
- `pyproject.toml` 新增 `redis`(async client,pin 明確版本,對齊 `00-overview/01-versions.md`)並 `uv lock`。

## Acceptance

- [ ] `cd backend && uv run alembic upgrade head` 成功;`uv run alembic downgrade -1` round-trip 無誤(表建/刪對稱,禁 DROP 以外的破壞)
- [ ] `uv run python -c "from app.models import RdsTableMeta"` 匯入成功且於 `models/__init__.py` 匯出
- [ ] `uv run pytest tests/test_models_v120.py` 全綠(至少驗:欄位存在、dataset StrEnum 值、唯一鍵約束)
- [ ] `uv run ruff check . && uv run mypy app` green
- [ ] `redis` 出現在 `pyproject.toml` 且 `uv.lock` 已更新(`grep -q '"redis"' uv.lock` 或對應鎖定條目存在)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/00-overview/01-versions.md`
- `docs/Design-Base/00-overview/05-timezone.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/01-identifiers.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/06-timezone.md`
- `docs/Design-Base/04-databases/08-alembic.md`
