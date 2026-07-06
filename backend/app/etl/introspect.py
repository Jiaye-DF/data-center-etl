"""來源 / 目標 RDS database 結構內省:列 schema / table / column,供前端瀏覽頁使用。

- 連線共用 `AWS_RDS_*`,database 由 dataset 決定(source→AWS_RDS_SOURCE_DB,
  target→AWS_RDS_TARGET_DB;見 reader.py)。
- 只讀 information_schema / pg catalog;schema / table 以 bind params 傳值(非識別字拼接),
  無注入風險(04-sql-safety.md)。
- row 數以 pg_class.reltuples 估算(禁對數千張表逐一 count(*),大表會很慢)。
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.etl.reader import rds_database_url

# dataset 名稱 → 對應 database 的 env key
DATASET_ENV_KEYS: dict[str, str] = {
    "source": "AWS_RDS_SOURCE_DB",
    "target": "AWS_RDS_TARGET_DB",
}

# 以 database env key 為鍵快取 engine(連線池重用;程序生命週期內共用)
_ENGINES: dict[str, AsyncEngine] = {}


def _get_engine(dataset: str) -> AsyncEngine:
    """取得指定 dataset 的 RDS engine(lazy 建立 + 快取)。"""
    env_key = DATASET_ENV_KEYS.get(dataset)
    if env_key is None:
        raise ValueError(f"未知 dataset:{dataset!r}(僅支援 source / target)")
    engine = _ENGINES.get(env_key)
    if engine is None:
        engine = create_async_engine(rds_database_url(env_key), pool_size=2, max_overflow=3)
        _ENGINES[env_key] = engine
    return engine


_SCHEMAS_SQL = text(
    """
    SELECT t.table_schema AS schema,
           count(*) AS table_count
    FROM information_schema.tables t
    WHERE t.table_type = 'BASE TABLE'
      AND t.table_schema NOT IN ('pg_catalog', 'information_schema')
    GROUP BY t.table_schema
    ORDER BY t.table_schema
    """
)

_TABLE_COUNT_SQL = text(
    """
    SELECT count(*) AS total
    FROM information_schema.tables
    WHERE table_type = 'BASE TABLE' AND table_schema = :schema
    """
)

_TABLES_SQL = text(
    """
    SELECT t.table_name AS name,
           (SELECT count(*) FROM information_schema.columns c
             WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name)
             AS column_count,
           COALESCE(pc.reltuples, 0)::bigint AS row_estimate
    FROM information_schema.tables t
    JOIN pg_namespace n ON n.nspname = t.table_schema
    LEFT JOIN pg_class pc ON pc.relname = t.table_name AND pc.relnamespace = n.oid
    WHERE t.table_schema = :schema AND t.table_type = 'BASE TABLE'
    ORDER BY t.table_name
    LIMIT :limit OFFSET :offset
    """
)

_COLUMNS_SQL = text(
    """
    SELECT column_name AS name,
           data_type,
           is_nullable = 'YES' AS nullable,
           ordinal_position
    FROM information_schema.columns
    WHERE table_schema = :schema AND table_name = :table
    ORDER BY ordinal_position
    """
)


async def list_schemas(dataset: str) -> list[dict[str, object]]:
    """列出 dataset 內所有非系統 schema 與各自的表數。"""
    async with _get_engine(dataset).connect() as conn:
        rows = (await conn.execute(_SCHEMAS_SQL)).mappings().all()
    return [dict(r) for r in rows]


async def list_tables(
    dataset: str, schema: str, *, page: int, page_size: int
) -> dict[str, object]:
    """分頁列出指定 schema 的表(含欄位數與 row 估算)。"""
    offset = (page - 1) * page_size
    async with _get_engine(dataset).connect() as conn:
        total = (await conn.execute(_TABLE_COUNT_SQL, {"schema": schema})).scalar_one()
        rows = (
            await conn.execute(
                _TABLES_SQL, {"schema": schema, "limit": page_size, "offset": offset}
            )
        ).mappings().all()
    return {
        "items": [dict(r) for r in rows],
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


async def list_columns(dataset: str, schema: str, table: str) -> list[dict[str, object]]:
    """列出指定表的欄位(名稱 / 型別 / 可空)。"""
    async with _get_engine(dataset).connect() as conn:
        rows = (
            await conn.execute(_COLUMNS_SQL, {"schema": schema, "table": table})
        ).mappings().all()
    return [dict(r) for r in rows]
