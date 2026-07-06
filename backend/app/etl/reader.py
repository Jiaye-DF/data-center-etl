"""來源端讀取:從 AWS RDS 來源 database 以 SQLAlchemy async(asyncpg)整表讀出。

- 連線一律由 env 注入,缺值 fail-fast;禁硬編、禁 log 帳密
  (`docs/Design-Base/00-overview/02-secrets.md`)。
- ETL 來源/目標同一 RDS 實例(`AWS_RDS_HOST/PORT/USER/PASSWORD` 共用),
  僅 database 不同(`AWS_RDS_SOURCE_DB` / `AWS_RDS_TARGET_DB`);
  與本專案自有 PostgreSQL(`POSTGRES_*` / `DATABASE_URL`)明確分離。
- SELECT 的 schema / table / column 識別字走白名單 + 引號跳脫(`04-sql-safety.md`)。
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.etl.comments import quote_ident

# ETL 來源 database 名稱的 env key(ERP 鏡像庫,如 erp_migration_test)
RDS_SOURCE_DB_ENV = "AWS_RDS_SOURCE_DB"


def require_env(key: str) -> str:
    """讀取必要 env,缺少即 fail-fast(訊息只含變數名,不含值)。"""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"缺少必要環境變數:{key}")
    return value


def rds_database_url(db_env_key: str) -> str:
    """由共用 `AWS_RDS_HOST/PORT/USER/PASSWORD` + 指定 database env 組 asyncpg 連線 URL。

    帳密僅進入回傳值供建立連線;呼叫端禁 log 完整 URL。
    """
    host = require_env("AWS_RDS_HOST")
    port = os.environ.get("AWS_RDS_PORT", "5432")
    user = require_env("AWS_RDS_USER")
    password = require_env("AWS_RDS_PASSWORD")
    name = require_env(db_env_key)
    return (
        f"postgresql+asyncpg://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(name)}"
    )


class PostgresSourceReader:
    """來源 DB 讀取器;連線 lazy 建立,env 缺值於首次使用時 fail-fast。"""

    def __init__(self, engine: AsyncEngine | None = None) -> None:
        self._engine = engine

    def _get_engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(rds_database_url(RDS_SOURCE_DB_ENV))
        return self._engine

    async def fetch_rows(
        self, schema: str, table: str, columns: Sequence[str]
    ) -> list[dict[str, Any]]:
        """SELECT 指定欄位整表讀出;識別字全走白名單引號化(無使用者輸入值,無 bind 需求)。"""
        select_list = ", ".join(quote_ident(col) for col in columns)
        sql = f"SELECT {select_list} FROM {quote_ident(schema)}.{quote_ident(table)}"
        async with self._get_engine().connect() as conn:
            result = await conn.execute(text(sql))
            return [dict(row) for row in result.mappings()]

    async def dispose(self) -> None:
        """釋放連線池(worker 收尾用)。"""
        if self._engine is not None:
            await self._engine.dispose()
