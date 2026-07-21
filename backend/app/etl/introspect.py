"""來源 / 目標 RDS database 結構內省:列 schema / table / column,供前端瀏覽頁使用。

- 連線共用 `AWS_RDS_*`,database 由 dataset 決定(source→AWS_RDS_SOURCE_DB,
  target→AWS_RDS_TARGET_DB;見 reader.py)。
- 只讀 information_schema / pg catalog;schema / table 以 bind params 傳值(非識別字拼接),
  無注入風險(04-sql-safety.md)。
- row 數以 pg_class.reltuples 估算(禁對數千張表逐一 count(*),大表會很慢)。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.etl.comments import quote_ident
from app.etl.reader import rds_database_url
from app.etl.semantic_schema import SEMANTIC_SCHEMA

# row 數上限:超過即以 1000+ 呈現(禁 COUNT(*),改 SELECT 1 ... LIMIT 1001 探測)
ROW_COUNT_CAP = 1000

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


logger = logging.getLogger(__name__)

# 排除非業務 schema:pg 系統、語意層 metadata(erp_metadata)、語意化 view 落點
# `*_view`(含 v1.5.0 舊制 `*_en`)——瀏覽 / 快照皆不應把系統結構列為資料分類。
# 注意(AD-129):後綴排除同時作用於 source 側 — 來源 schema 命名不得以 `_view` / `_en`
# 結尾,否則會被靜默排除(永不納入快照 / 同步);snapshot_tables 對此類排除補 info log 供診斷。
_EXCLUDED_SCHEMA_CONDS = f"""
      AND t.table_schema NOT IN ('pg_catalog', 'information_schema', '{SEMANTIC_SCHEMA}')
      AND t.table_schema NOT LIKE '%\\_view' ESCAPE '\\'
      AND t.table_schema NOT LIKE '%\\_en' ESCAPE '\\'
"""

_SCHEMAS_SQL = text(
    f"""
    SELECT t.table_schema AS schema,
           count(*) AS table_count
    FROM information_schema.tables t
    WHERE t.table_type = 'BASE TABLE'
{_EXCLUDED_SCHEMA_CONDS}
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
             AS column_count
    FROM information_schema.tables t
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


async def _bounded_row_counts(
    conn: AsyncConnection, schema: str, names: list[str]
) -> dict[str, int]:
    """一次 UNION ALL 探測整頁各表的 row 數(每表 SELECT 1 ... LIMIT CAP+1,禁 COUNT(*))。

    回傳值上限為 CAP+1:值 > CAP 代表「超過上限」,呈現端顯示 1000+。
    """
    if not names:
        return {}
    limit = ROW_COUNT_CAP + 1
    parts: list[str] = []
    params: dict[str, object] = {}
    for i, name in enumerate(names):
        qualified = f"{quote_ident(schema)}.{quote_ident(name)}"
        # 識別字走白名單引號化(來自 information_schema,再引號化雙保險);表名另以 bind 值回傳對應
        parts.append(
            f"SELECT :n{i} AS name, "
            f"(SELECT count(*) FROM (SELECT 1 FROM {qualified} LIMIT {limit}) s) AS c"
        )
        params[f"n{i}"] = name
    sql = text(" UNION ALL ".join(parts))
    rows = (await conn.execute(sql, params)).mappings().all()
    return {str(r["name"]): int(r["c"]) for r in rows}


async def list_tables(
    dataset: str, schema: str, *, page: int, page_size: int
) -> dict[str, object]:
    """分頁列出指定 schema 的表(含欄位數與 bounded row 數)。"""
    offset = (page - 1) * page_size
    async with _get_engine(dataset).connect() as conn:
        total = (await conn.execute(_TABLE_COUNT_SQL, {"schema": schema})).scalar_one()
        rows = (
            await conn.execute(
                _TABLES_SQL, {"schema": schema, "limit": page_size, "offset": offset}
            )
        ).mappings().all()
        names = [str(r["name"]) for r in rows]
        counts = await _bounded_row_counts(conn, schema, names)
    items = [
        {
            "name": str(r["name"]),
            "column_count": int(r["column_count"]),
            "row_count": counts.get(str(r["name"]), 0),
        }
        for r in rows
    ]
    return {
        "items": items,
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


# snapshot 用:一次列全 schema 全 base table + 欄位數(供 rds_table_meta 快照落地)
_ALL_TABLES_SQL = text(
    f"""
    SELECT t.table_schema AS schema,
           t.table_name AS name,
           (SELECT count(*) FROM information_schema.columns c
             WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name)
             AS column_count
    FROM information_schema.tables t
    WHERE t.table_type = 'BASE TABLE'
{_EXCLUDED_SCHEMA_CONDS}
    ORDER BY t.table_schema, t.table_name
    """
)

# AD-129 診斷:被後綴保留字(_view/_en)排除、且非 erp_metadata 的 schema
# (快照 refresh 時 log info 一次,避免來源業務 schema 撞名被靜默吃掉無從察覺)
_SUFFIX_EXCLUDED_SCHEMAS_SQL = text(
    f"""
    SELECT DISTINCT t.table_schema AS schema
    FROM information_schema.tables t
    WHERE t.table_type = 'BASE TABLE'
      AND t.table_schema NOT IN ('pg_catalog', 'information_schema', '{SEMANTIC_SCHEMA}')
      AND (t.table_schema LIKE '%\\_view' ESCAPE '\\'
           OR t.table_schema LIKE '%\\_en' ESCAPE '\\')
    ORDER BY 1
    """
)

# bounded row 探測單批表數上限(表數多時避免單條 UNION ALL 過長)
_ROW_PROBE_CHUNK = 50


def get_engine(dataset: str) -> AsyncEngine:
    """取得 dataset 的 RDS engine(快照服務重用連線池;對外公開包裝,語意同 `_get_engine`)。"""
    return _get_engine(dataset)


# 快照進度回報 callback:(已探測表數, 總表數);由呼叫端決定落地方式(如寫 Redis)
ProgressCallback = Callable[[int, int], Awaitable[None]]


async def snapshot_tables(
    conn: AsyncConnection, on_progress: ProgressCallback | None = None
) -> list[dict[str, int | str]]:
    """一次列全 schema 全 base table + 欄位數 + bounded row 數(供 metadata 快照)。

    row 數沿用 `_bounded_row_counts` 的 `SELECT 1 ... LIMIT` 探測(禁 COUNT(*));
    表數多時分批探測,避免單條 UNION ALL 過長。連線由呼叫端提供(供 refresh 於同連線續查字典)。
    `on_progress` 每探測完一批呼叫一次(row 探測為 refresh 最耗時階段,供進度條顯示)。
    """
    # AD-129:後綴保留字排除的 schema 補診斷 log(靜默排除無從察覺誤殺)
    excluded = (await conn.execute(_SUFFIX_EXCLUDED_SCHEMAS_SQL)).scalars().all()
    if excluded:
        logger.info(
            "內省排除 %d 個後綴保留字 schema(_view/_en 結尾不納入快照):%s",
            len(excluded),
            ", ".join(str(s) for s in excluded),
        )
    rows = (await conn.execute(_ALL_TABLES_SQL)).mappings().all()
    names_by_schema: dict[str, list[str]] = {}
    column_counts: dict[tuple[str, str], int] = {}
    for r in rows:
        schema = str(r["schema"])
        name = str(r["name"])
        names_by_schema.setdefault(schema, []).append(name)
        column_counts[(schema, name)] = int(r["column_count"])

    result: list[dict[str, int | str]] = []
    total = len(rows)
    probed = 0
    for schema, names in names_by_schema.items():
        row_counts: dict[str, int] = {}
        for start in range(0, len(names), _ROW_PROBE_CHUNK):
            chunk = names[start : start + _ROW_PROBE_CHUNK]
            row_counts.update(await _bounded_row_counts(conn, schema, chunk))
            probed += len(chunk)
            if on_progress is not None:
                await on_progress(probed, total)
        for name in names:
            result.append(
                {
                    "schema": schema,
                    "name": name,
                    "column_count": column_counts[(schema, name)],
                    "row_count": row_counts.get(name, 0),
                }
            )
    return result
