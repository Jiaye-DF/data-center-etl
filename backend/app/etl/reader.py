"""來源端讀取:從 `erp_migration_test` 以 SQLAlchemy async(asyncpg)整表讀出。

- 連線一律由 env 注入(`SOURCE_DB_*`),缺值 fail-fast;禁硬編、禁 log 帳密
  (`docs/Design-Base/00-overview/02-secrets.md`)。
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

# 來源 DB(erp_migration_test)env 變數前綴
SOURCE_ENV_PREFIX = "SOURCE_DB"


def require_env(key: str) -> str:
    """讀取必要 env,缺少即 fail-fast(訊息只含變數名,不含值)。"""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"缺少必要環境變數:{key}")
    return value


def database_url_from_env(prefix: str) -> str:
    """由 `<PREFIX>_HOST/PORT/NAME/USER/PASSWORD` 組 asyncpg 連線 URL。

    帳密僅進入回傳值供建立連線;呼叫端禁 log 完整 URL。
    """
    host = require_env(f"{prefix}_HOST")
    port = os.environ.get(f"{prefix}_PORT", "5432")
    name = require_env(f"{prefix}_NAME")
    user = require_env(f"{prefix}_USER")
    password = require_env(f"{prefix}_PASSWORD")
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
            self._engine = create_async_engine(database_url_from_env(SOURCE_ENV_PREFIX))
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
