"""目標端寫入:把轉換後資料落地到 AWS RDS 目標 database,並逐條套 COMMENT ON COLUMN。

- 寫入策略禁 DROP:表已存在 → TRUNCATE + INSERT(保留結構與既有 Comment);
  不存在 → CREATE TABLE(欄位型別由 mapping 的 transform_type 決定)。
- 連線一律由 env 注入,缺值 fail-fast;禁硬編、禁 log 帳密
  (`docs/Design-Base/00-overview/02-secrets.md`)。
- 連線組(host/port/user/password)與來源共用 `AWS_RDS_*`,
  僅 database 由 `AWS_RDS_TARGET_DB` 指定(見 reader.py)。
- DDL 識別字走白名單引號化;INSERT 值走 bind params(`04-sql-safety.md`)。
"""

from __future__ import annotations

from collections.abc import AsyncIterable, Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.etl.comments import quote_ident
from app.etl.reader import rds_database_url

# ETL 目標 database 名稱的 env key(資料中心庫,如 erp_etl_hub_test)
RDS_TARGET_DB_ENV = "AWS_RDS_TARGET_DB"

# transform_type → PostgreSQL 欄位型別;NULL / 未知型別以 TEXT 落地
_TYPE_MAP: dict[str, str] = {
    "int": "BIGINT",
    "float": "DOUBLE PRECISION",
    "str": "TEXT",
}
_DEFAULT_SQL_TYPE = "TEXT"


def column_sql_type(transform_type: str | None) -> str:
    """由 mapping 的 transform_type 對映 CREATE TABLE 欄位型別。"""
    if transform_type is None:
        return _DEFAULT_SQL_TYPE
    return _TYPE_MAP.get(transform_type, _DEFAULT_SQL_TYPE)


class PostgresTargetWriter:
    """目標 DB 寫入器;連線 lazy 建立,env 缺值於首次使用時 fail-fast。"""

    def __init__(self, engine: AsyncEngine | None = None) -> None:
        self._engine = engine

    def _get_engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(rds_database_url(RDS_TARGET_DB_ENV))
        return self._engine

    async def write_table(
        self,
        *,
        schema: str,
        table: str,
        columns: Sequence[str],
        column_types: Mapping[str, str | None],
        row_batches: AsyncIterable[Sequence[Mapping[str, object]]],
        comment_statements: Sequence[str],
    ) -> int:
        """單一交易內完成:確保表存在(禁 DROP)→ 清空後逐批重灌 → 套欄位 Comment。

        row_batches 為分批迭代器(scan AD-006:禁整表物化,記憶體占用僅單批);
        單交易保原子性 — 中途失敗(含來源讀取例外)整批 rollback,TRUNCATE 一併復原。
        回傳實際寫入筆數。comment_statements 由 engine 以
        `comments.build_column_comments` 產出(缺 comment 已於 engine 端 fail)。
        """
        qualified = f"{quote_ident(schema)}.{quote_ident(table)}"
        written = 0
        async with self._get_engine().begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quote_ident(schema)}"))
            exists = await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables"
                    " WHERE table_schema = :schema AND table_name = :table"
                ).bindparams(schema=schema, table=table)
            )
            if exists.first() is not None:
                # 禁 DROP:既有表僅清空重灌,保留結構與既有 Comment
                await conn.execute(text(f"TRUNCATE TABLE {qualified}"))
            else:
                col_defs = ", ".join(
                    f"{quote_ident(col)} {column_sql_type(column_types.get(col))}"
                    for col in columns
                )
                await conn.execute(text(f"CREATE TABLE {qualified} ({col_defs})"))

            # 欄名經白名單驗證;值一律 bind params(:c0..:cN)
            col_list = ", ".join(quote_ident(col) for col in columns)
            placeholders = ", ".join(f":c{i}" for i in range(len(columns)))
            insert_sql = text(f"INSERT INTO {qualified} ({col_list}) VALUES ({placeholders})")
            async for batch in row_batches:
                if not batch:
                    continue
                params = [
                    {f"c{i}": row.get(col) for i, col in enumerate(columns)} for row in batch
                ]
                await conn.execute(insert_sql, params)
                written += len(batch)

            for stmt in comment_statements:
                # COMMENT 為已跳脫完成的 DDL 成品字串;不得再經 text() 解析,
                # 否則內容含 :xxx(如 "Y":1)會被誤判為 bind 參數而 raise
                await conn.exec_driver_sql(stmt)
        return written

    async def dispose(self) -> None:
        """釋放連線池(worker 收尾用)。"""
        if self._engine is not None:
            await self._engine.dispose()
