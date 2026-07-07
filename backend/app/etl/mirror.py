"""自動鏡像引擎:內省來源真實型別 → 目標保留型別建表 + TRUNCATE + 分批 INSERT → 套 DS 字典 COMMENT。

獨立於 config-driven 引擎(不動 engine/reader/writer/comments/introspect);唯讀重用
`reader.rds_database_url` 建立來源 / 目標連線。

- **禁 DROP**:目標表存在 → `TRUNCATE`;不存在 → `CREATE TABLE`(保留來源 varchar 長度 /
  numeric precision/scale)。任何情況不得 DROP TABLE / DROP COLUMN。
- 禁整表物化:server-side cursor 分批讀 + 分批 INSERT(scan AD-006)。
- COMMENT 放寬:字典無對應之表 / 欄略過該 COMMENT,不 raise。
- 識別字白名單引號化,值走 bind params(`04-sql-safety.md`);機密不 log。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.etl.comments import quote_ident, quote_literal
from app.etl.dictionary import fetch_column_comments, fetch_table_comment
from app.etl.reader import DEFAULT_BATCH_SIZE, RDS_SOURCE_DB_ENV, rds_database_url
from app.etl.writer import RDS_TARGET_DB_ENV

logger = logging.getLogger(__name__)

# 字典先落地:full mirror 時 DS schema(含 GAT/GAQ 字典表)排最前,其餘依名
DS_SCHEMA = "DS"


@dataclass(frozen=True)
class MirrorColumn:
    """來源欄位的鏡像規格:欄名 + 重建後的目標 DDL 型別片段(如 `VARCHAR(10)`)。"""

    name: str
    type_sql: str


@dataclass(frozen=True)
class TableStat:
    """來源表寫入計數器 signature(pg_stat_user_tables 累計值)。"""

    n_tup_ins: int
    n_tup_upd: int
    n_tup_del: int


_SOURCE_TABLES_SQL = text(
    """
    SELECT table_schema AS schema, table_name AS name
    FROM information_schema.tables
    WHERE table_type = 'BASE TABLE'
      AND table_schema NOT IN ('pg_catalog', 'information_schema')
    """
)

_SOURCE_COLUMNS_SQL = text(
    """
    SELECT column_name,
           data_type,
           character_maximum_length,
           numeric_precision,
           numeric_scale
    FROM information_schema.columns
    WHERE table_schema = :schema AND table_name = :table
    ORDER BY ordinal_position
    """
)

_TARGET_TABLE_EXISTS_SQL = text(
    "SELECT 1 FROM information_schema.tables"
    " WHERE table_schema = :schema AND table_name = :table"
)

_SOURCE_STATS_SQL = text(
    "SELECT schemaname AS schema, relname AS name,"
    " n_tup_ins, n_tup_upd, n_tup_del FROM pg_stat_user_tables"
)


def _as_int(value: object) -> int | None:
    """information_schema 的長度 / 精度欄位取整;非整數(含 None)回 None。"""
    return value if isinstance(value, int) else None


def sort_source_tables(rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, str]]:
    """(schema, table) 排序:DS schema 全數排最前(字典先落地),其餘依 schema / 名。"""
    return sorted(
        ((str(r["schema"]), str(r["name"])) for r in rows),
        key=lambda st: (0 if st[0] == DS_SCHEMA else 1, st[0], st[1]),
    )


def stat_changed(current: TableStat, baseline: TableStat | None) -> bool:
    """判斷來源表自上次同步後是否變動。

    - baseline 為 None(首次上線 / 來源新表,尚無基準)→ 視為變動(需整灌建基準)。
    - current != baseline → 變動:計數器任一「增加」代表有增/改/刪;任一「倒退」
      (來源重啟 / crash / pg_stat_reset 歸零)保守亦視為變動(寧可多做不可漏做)。
    - 三者皆相等 → 未變動,本輪跳過。
    """
    return baseline is None or current != baseline


def rows_to_stats(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], TableStat]:
    """pg_stat_user_tables 查詢結果 → `{(schema, name): TableStat}`;counter 為 None 落 0。"""
    return {
        (str(r["schema"]), str(r["name"])): TableStat(
            n_tup_ins=int(r["n_tup_ins"] or 0),
            n_tup_upd=int(r["n_tup_upd"] or 0),
            n_tup_del=int(r["n_tup_del"] or 0),
        )
        for r in rows
    }


def source_type_to_ddl(row: Mapping[str, Any]) -> str:
    """由來源 information_schema.columns 一列重建目標 DDL 型別(保留長度 / 精度)。

    未知型別保守落 TEXT 並記 log(不含機密)。
    """
    data_type = str(row["data_type"])
    char_len = _as_int(row["character_maximum_length"])
    num_prec = _as_int(row["numeric_precision"])
    num_scale = _as_int(row["numeric_scale"])

    match data_type:
        case "character varying":
            return f"VARCHAR({char_len})" if char_len is not None else "VARCHAR"
        case "character":
            return f"CHAR({char_len})" if char_len is not None else "CHAR"
        case "text":
            return "TEXT"
        case "numeric" | "decimal":
            if num_prec is not None and num_scale is not None:
                return f"NUMERIC({num_prec},{num_scale})"
            if num_prec is not None:
                return f"NUMERIC({num_prec})"
            return "NUMERIC"
        case "smallint":
            return "SMALLINT"
        case "integer":
            return "INTEGER"
        case "bigint":
            return "BIGINT"
        case "boolean":
            return "BOOLEAN"
        case "real":
            return "REAL"
        case "double precision":
            return "DOUBLE PRECISION"
        case "date":
            return "DATE"
        case "timestamp without time zone":
            return "TIMESTAMP"
        case "timestamp with time zone":
            return "TIMESTAMPTZ"
        case "time without time zone":
            return "TIME"
        case "time with time zone":
            return "TIMETZ"
        case "bytea":
            return "BYTEA"
        case "uuid":
            return "UUID"
        case "json":
            return "JSON"
        case "jsonb":
            return "JSONB"
        case _:
            logger.warning("未知來源型別 %r → 保守落 TEXT", data_type)
            return "TEXT"


def build_comment_statements(
    schema: str,
    table: str,
    columns: Sequence[str],
    table_comment: str | None,
    column_comments: Mapping[str, str],
) -> list[str]:
    """組 COMMENT ON TABLE / COLUMN;無對應者略過(comment 放寬,不 raise)。

    column_comments 以小寫欄名為 key;識別字白名單引號化,描述單引號跳脫。
    """
    qualified = f"{quote_ident(schema)}.{quote_ident(table)}"
    stmts: list[str] = []
    if table_comment and table_comment.strip():
        stmts.append(f"COMMENT ON TABLE {qualified} IS {quote_literal(table_comment.strip())};")
    for col in columns:
        desc = column_comments.get(col.lower())
        if desc and desc.strip():
            target = f"{qualified}.{quote_ident(col)}"
            stmts.append(f"COMMENT ON COLUMN {target} IS {quote_literal(desc.strip())};")
    return stmts


async def write_mirror(
    conn: AsyncConnection,
    *,
    schema: str,
    table: str,
    columns: Sequence[MirrorColumn],
    row_batches: AsyncIterable[Sequence[Mapping[str, object]]],
    table_comment: str | None,
    column_comments: Mapping[str, str],
) -> int:
    """單一目標交易內:建 schema → 不存在建表 / 存在 TRUNCATE(禁 DROP)→ 分批 INSERT → 套 COMMENT。

    row_batches 為分批迭代器(scan AD-006:禁整表物化);回傳實際寫入筆數。
    """
    qualified = f"{quote_ident(schema)}.{quote_ident(table)}"
    colnames = [c.name for c in columns]

    await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quote_ident(schema)}"))
    exists = (
        await conn.execute(
            _TARGET_TABLE_EXISTS_SQL.bindparams(schema=schema, table=table)
        )
    ).first()
    if exists is not None:
        # 禁 DROP:既有表僅清空重灌,保留結構
        await conn.execute(text(f"TRUNCATE TABLE {qualified}"))
    else:
        col_defs = ", ".join(f"{quote_ident(c.name)} {c.type_sql}" for c in columns)
        await conn.execute(text(f"CREATE TABLE {qualified} ({col_defs})"))

    col_list = ", ".join(quote_ident(c) for c in colnames)
    placeholders = ", ".join(f":c{i}" for i in range(len(colnames)))
    insert_sql = text(f"INSERT INTO {qualified} ({col_list}) VALUES ({placeholders})")
    written = 0
    async for batch in row_batches:
        if not batch:
            continue
        params = [
            {f"c{i}": row.get(col) for i, col in enumerate(colnames)} for row in batch
        ]
        await conn.execute(insert_sql, params)
        written += len(batch)

    for stmt in build_comment_statements(
        schema, table, colnames, table_comment, column_comments
    ):
        await conn.execute(text(stmt))
    return written


class MirrorEngine:
    """自動鏡像引擎:來源 / 目標連線 lazy 建立,env 缺值於首次使用時 fail-fast。"""

    def __init__(
        self,
        source_engine: AsyncEngine | None = None,
        target_engine: AsyncEngine | None = None,
    ) -> None:
        self._source_engine_obj = source_engine
        self._target_engine_obj = target_engine

    def _source_engine(self) -> AsyncEngine:
        if self._source_engine_obj is None:
            self._source_engine_obj = create_async_engine(
                rds_database_url(RDS_SOURCE_DB_ENV)
            )
        return self._source_engine_obj

    def _target_engine(self) -> AsyncEngine:
        if self._target_engine_obj is None:
            self._target_engine_obj = create_async_engine(
                rds_database_url(RDS_TARGET_DB_ENV)
            )
        return self._target_engine_obj

    async def list_source_tables(self) -> list[tuple[str, str]]:
        """列來源所有非系統 schema 的 base table;DS schema 排最前,其餘依名。"""
        async with self._source_engine().connect() as conn:
            rows = [
                dict(r) for r in (await conn.execute(_SOURCE_TABLES_SQL)).mappings().all()
            ]
        return sort_source_tables(rows)

    async def fetch_source_stats(self) -> dict[tuple[str, str], TableStat]:
        """一次 query 取來源所有表的累計寫入計數器(零掃表);key 為 (schema, table)。"""
        async with self._source_engine().connect() as conn:
            rows = [
                dict(r) for r in (await conn.execute(_SOURCE_STATS_SQL)).mappings().all()
            ]
        return rows_to_stats(rows)

    async def _introspect_columns(
        self, conn: AsyncConnection, schema: str, table: str
    ) -> list[MirrorColumn]:
        rows = [
            dict(r)
            for r in (
                await conn.execute(_SOURCE_COLUMNS_SQL, {"schema": schema, "table": table})
            ).mappings().all()
        ]
        return [
            MirrorColumn(name=str(r["column_name"]), type_sql=source_type_to_ddl(r))
            for r in rows
        ]

    async def mirror_table(
        self, schema: str, table: str, *, batch_size: int = DEFAULT_BATCH_SIZE
    ) -> int:
        """鏡像單表:內省型別 → 目標保留型別建表 / TRUNCATE → 分批灌 → 套字典 COMMENT。回傳筆數。"""
        async with self._source_engine().connect() as source_conn:
            columns = await self._introspect_columns(source_conn, schema, table)
            if not columns:
                raise ValueError(f"來源表無欄位或不存在:{schema}.{table}")
            colnames = [c.name for c in columns]
            table_comment = await fetch_table_comment(source_conn, table)
            column_comments = await fetch_column_comments(source_conn, colnames)

            select_list = ", ".join(quote_ident(c) for c in colnames)
            stream_sql = text(
                f"SELECT {select_list} FROM {quote_ident(schema)}.{quote_ident(table)}"
            )

            async def _row_batches() -> AsyncIterable[list[dict[str, object]]]:
                result = await source_conn.stream(stream_sql)
                async for partition in result.mappings().partitions(batch_size):
                    yield [dict(row) for row in partition]

            async with self._target_engine().begin() as target_conn:
                written = await write_mirror(
                    target_conn,
                    schema=schema,
                    table=table,
                    columns=columns,
                    row_batches=_row_batches(),
                    table_comment=table_comment,
                    column_comments=column_comments,
                )
        logger.info("鏡像完成:%s.%s(%d 筆)", schema, table, written)
        return written

    async def dispose(self) -> None:
        """釋放來源 / 目標連線池(worker 收尾用)。"""
        if self._source_engine_obj is not None:
            await self._source_engine_obj.dispose()
        if self._target_engine_obj is not None:
            await self._target_engine_obj.dispose()
