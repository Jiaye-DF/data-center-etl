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

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.etl.comments import quote_ident

logger = logging.getLogger(__name__)

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
        updated_by uuid NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
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

# v1.5.1 fixed #3:updated_by 由 text 冪等轉 uuid(對齊 04-databases 必備欄位型別;
# 合法 UUID 字串原值轉型,工具標記等非 UUID 值一律轉系統帳號全零 UUID,NULL 保留)
_UPDATED_BY_TYPE_SQL = text(
    "SELECT data_type FROM information_schema.columns"
    " WHERE table_schema = :s AND table_name = :t AND column_name = 'updated_by'"
)

_UUID_REGEX = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

# 系統帳號全零 UUID(user 決議 2026-07-21:updated_by 無值一律填全零,欄位 NOT NULL DEFAULT)
_ZERO_UUID = "00000000-0000-0000-0000-000000000000"

_MIGRATE_UPDATED_BY_SQL = text(
    f"""
    ALTER TABLE {_QUALIFIED}
        ALTER COLUMN updated_by TYPE uuid
            USING (CASE
                WHEN updated_by IS NULL THEN NULL
                WHEN updated_by ~ '{_UUID_REGEX}' THEN updated_by::uuid
                ELSE '{_ZERO_UUID}'::uuid
            END)
    """
)

# 既有 NULL 回填全零 + 補上 DEFAULT / NOT NULL(冪等:僅欄位仍可 NULL 時執行)
_UPDATED_BY_NULLABLE_SQL = text(
    "SELECT is_nullable FROM information_schema.columns"
    " WHERE table_schema = :s AND table_name = :t AND column_name = 'updated_by'"
)

_BACKFILL_UPDATED_BY_SQL = text(
    f"UPDATE {_QUALIFIED} SET updated_by = '{_ZERO_UUID}'::uuid WHERE updated_by IS NULL"
)

_ENFORCE_UPDATED_BY_SQL = text(
    f"""
    ALTER TABLE {_QUALIFIED}
        ALTER COLUMN updated_by SET DEFAULT '{_ZERO_UUID}'::uuid,
        ALTER COLUMN updated_by SET NOT NULL
    """
)

_MIGRATE_UPDATED_AT_SQL = text(
    f"""
    ALTER TABLE {_QUALIFIED}
        ALTER COLUMN updated_at TYPE timestamp
            USING (updated_at AT TIME ZONE 'Asia/Taipei'),
        ALTER COLUMN updated_at SET DEFAULT (now() AT TIME ZONE 'Asia/Taipei')
    """
)

# v1.6.1 fixed AD-154 / AD-150:表層級英文名(column_name = '')為權限授權的引用鍵
# (`client_setting.*_items.table_name` 存的就是它),必須全域唯一 —— 否則 A 表英文名改成
# B 表原名時,既有授權會靜默改指向另一張表。
_ENGLISH_TABLE_UNIQUE_INDEX = "uq_semantic_mappings_english_table"

_ENGLISH_TABLE_DUPLICATE_SQL = text(
    f"SELECT english_name, count(*) AS n FROM {_QUALIFIED}"
    " WHERE column_name = '' GROUP BY english_name HAVING count(*) > 1"
    " ORDER BY english_name"
)

_ENGLISH_TABLE_UNIQUE_SQL = text(
    f"CREATE UNIQUE INDEX IF NOT EXISTS {_ENGLISH_TABLE_UNIQUE_INDEX}"
    f" ON {_QUALIFIED} (english_name) WHERE column_name = ''"
)


async def ensure_semantic_schema(conn: AsyncConnection) -> None:
    """冪等建置 `erp_metadata.semantic_mappings`:存在則略過,不刪除既有結構。

    另冪等遷移舊版欄位型別(USING 轉換保留既有資料,已是目標型別則不動作):
    - `updated_at`:timestamptz → timestamp(UTC+8 naive,datetime2 等價)。
    - `updated_by`:text → uuid(v1.5.1 fixed #3;非 UUID 的工具標記轉系統全零 UUID)。

    最後補表層級英文名的全域唯一索引(AD-154);既有資料已有重複時只 log warning 並跳過,
    不讓啟動 / 建置流程炸掉 —— 人工清重後下次 ensure 會自動補上。
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
    row = (
        await conn.execute(
            _UPDATED_BY_TYPE_SQL, {"s": SEMANTIC_SCHEMA, "t": SEMANTIC_TABLE}
        )
    ).first()
    if row is not None and row[0] == "text":
        await conn.execute(_MIGRATE_UPDATED_BY_SQL)
    row = (
        await conn.execute(
            _UPDATED_BY_NULLABLE_SQL, {"s": SEMANTIC_SCHEMA, "t": SEMANTIC_TABLE}
        )
    ).first()
    if row is not None and row[0] == "YES":
        await conn.execute(_BACKFILL_UPDATED_BY_SQL)
        await conn.execute(_ENFORCE_UPDATED_BY_SQL)
    await _ensure_english_table_unique(conn)


async def _ensure_english_table_unique(conn: AsyncConnection) -> None:
    """建立表層級英文名唯一索引;現存重複值則列明並跳過(不擋建置流程)。"""
    duplicates = (await conn.execute(_ENGLISH_TABLE_DUPLICATE_SQL)).all()
    if duplicates:
        logger.warning(
            "semantic_mappings 表層級英文名有重複,略過建立唯一索引 %s;"
            "請人工清重後重跑 ensure(重複值:%s)",
            _ENGLISH_TABLE_UNIQUE_INDEX,
            ", ".join(f"{row[0]}×{row[1]}" for row in duplicates),
        )
        return
    await conn.execute(_ENGLISH_TABLE_UNIQUE_SQL)
