"""目標 RDS `erp_metadata.semantic_mappings` 冪等建置(task-001,propose A1)。

欄位語意層唯一事實來源:記錄 ERP 表 / 欄位的英文名、中文名與審核狀態(draft/confirmed)。
冪等:`CREATE SCHEMA IF NOT EXISTS` + `CREATE TABLE IF NOT EXISTS`,存在即略過,不刪除既有結構。
連線沿用 `app.etl.reader.rds_database_url`(與 mirror 引擎同模式,指向目標 RDS)。

時間欄位(user 決議 2026-07-20):RDS PG 端一律用 `timestamp`(無時區,即 MSSQL datetime2 等價),
值存 UTC+8 naive(`00-overview/05-timezone.md`);RDS 系統時鐘為 UTC,故 DEFAULT 需
`now() AT TIME ZONE 'Asia/Taipei'` 轉出本地 naive 值。既有舊版 timestamptz 欄位由
ensure 冪等偵測並就地轉型(ALTER TYPE + USING 保資料,非破壞性)。

**注意**:此表位於目標 RDS,DDL 不走 alembic(alembic 只管本專案自有 DB);
識別字為白名單常值(schema / table / column 名皆固定字面量),不接受使用者輸入,
對齊 `docs/Design-Base/04-databases/04-sql-safety.md`。
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.etl.comments import quote_ident

# 目標 schema / 表名:語意層唯一事實來源
SEMANTIC_SCHEMA = "erp_metadata"
SEMANTIC_TABLE = "semantic_mappings"

_QUALIFIED = f"{quote_ident(SEMANTIC_SCHEMA)}.{quote_ident(SEMANTIC_TABLE)}"

# 表結構(propose A1,一字不差):column_name 預設 '' 代表表層級映射;
# status 以 CHECK 限定 draft/confirmed,拒絕其他值
_CREATE_TABLE_SQL = text(
    f"""
    CREATE TABLE IF NOT EXISTS {_QUALIFIED} (
        table_name text NOT NULL,
        column_name text NOT NULL DEFAULT '',
        english_name text NOT NULL,
        zh_name text,
        status text NOT NULL DEFAULT 'draft'
            CONSTRAINT ck_semantic_mappings_status CHECK (status IN ('draft', 'confirmed')),
        updated_by text,
        updated_at timestamp NOT NULL DEFAULT (now() AT TIME ZONE 'Asia/Taipei'),
        PRIMARY KEY (table_name, column_name)
    )
    """
)

# 舊版部署過 timestamptz 的表:查型別後就地轉為 timestamp(UTC+8 naive),保留既有資料
_UPDATED_AT_TYPE_SQL = text(
    "SELECT data_type FROM information_schema.columns"
    " WHERE table_schema = :s AND table_name = :t AND column_name = 'updated_at'"
)

_MIGRATE_UPDATED_AT_SQL = text(
    f"""
    ALTER TABLE {_QUALIFIED}
        ALTER COLUMN updated_at TYPE timestamp
            USING (updated_at AT TIME ZONE 'Asia/Taipei'),
        ALTER COLUMN updated_at SET DEFAULT (now() AT TIME ZONE 'Asia/Taipei')
    """
)


async def ensure_semantic_schema(conn: AsyncConnection) -> None:
    """冪等建置 `erp_metadata.semantic_mappings`:存在則略過,不刪除既有結構。

    另冪等遷移舊版 `updated_at` 型別:偵測到 timestamptz 即轉為 timestamp(UTC+8 naive,
    datetime2 等價;USING 轉換保留既有資料),已是 timestamp 則不動作。
    """
    await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quote_ident(SEMANTIC_SCHEMA)}"))
    await conn.execute(_CREATE_TABLE_SQL)
    row = (
        await conn.execute(
            _UPDATED_AT_TYPE_SQL, {"s": SEMANTIC_SCHEMA, "t": SEMANTIC_TABLE}
        )
    ).first()
    if row is not None and row[0] == "timestamp with time zone":
        await conn.execute(_MIGRATE_UPDATED_AT_SQL)
