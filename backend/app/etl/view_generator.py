"""語意化 view 產生器(task-005,propose A4)。

以本地副本(task-003 `semantic_mappings`)的 confirmed 映射,迴圈目標 RDS 各帳套 schema,
對「該 schema 實際存在且有 confirmed 表層級映射」的表產生 `<schema>_en.<english_table>`
語意化 view;schema 差異只在 view 層處理,不動鏡像表結構本身。

- 只用 confirmed 列;draft 一律不進 view。表層級(`column_name=''`)決定 view 名,
  欄層級決定 SELECT alias。
- 迴圈以目標 RDS `information_schema` 內省得到的實際帳套 schema 為準(排除 DS /
  erp_metadata / 自身 `*_en`);跨帳套共用主檔(propose A4:GEM/GEN/ABM 集中託管 G2203、
  M2201/S2202 為 synonym)不需特判 — 只看「該 schema 實際存在的表」即自然涵蓋。
- 表實際欄位 ∩ confirmed 欄位;交集為空跳過該表。
- 不刪表:僅 `CREATE SCHEMA IF NOT EXISTS` + `CREATE OR REPLACE VIEW`;僅當 REPLACE 失敗
  確認為「欄位集合不相容」(Postgres SQLSTATE 42P16,既有 view 欄名 / 順序不可變更)時,
  才退回「DROP VIEW IF EXISTS + CREATE VIEW」重建流程 — 僅限本情境,且僅 DROP VIEW,
  不動任何表(`04-sql-safety.md` 禁字串拼接;識別字全走白名單 `quote_ident`)。其他例外
  (權限 / 暫時性錯誤等)一律往上拋,交由呼叫端記 warning 並保留原 view,避免任意例外
  都觸發 DROP 導致 view 永久消失(AD-112)。
- 重生觸發:mapping「內容簽名」(排序後正規化字串的 sha256)與上次相比有變才重生,否則
  略過。刻意不用本地 `updated_at`(整表重灌每輪都會刷新該欄位,無法反映內容是否真的
  變動);簽名存 Redis(對齊既有 `app.core.redis` 快取慣例)。單表產生失敗不中斷整輪,
  但**僅全部表都成功才寫入簽名**;有失敗則不更新簽名,讓下輪重試補齊缺漏的 view
  (AD-113:避免部分失敗被簽名長期抑制重試)。
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable, Mapping, Sequence

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, create_async_engine

from app.core import redis as cache
from app.etl.comments import quote_ident
from app.etl.mirror import DS_SCHEMA
from app.etl.reader import rds_database_url
from app.etl.semantic_schema import SEMANTIC_SCHEMA
from app.etl.writer import RDS_TARGET_DB_ENV
from app.models.semantic_mapping import SemanticMapping
from app.repositories.semantic_mapping_repo import SemanticMappingRepository

logger = logging.getLogger(__name__)

# view schema 命名慣例:帳套 schema 的語意化 view 落在 `<schema>_en`
VIEW_SCHEMA_SUFFIX = "_en"

# Postgres SQLSTATE:CREATE OR REPLACE VIEW 因既有 view 欄名 / 型別 / 順序不可變更而拒絕
# (「欄位集合不相容」,AD-112)——僅此代碼才允許走 DROP VIEW + CREATE 重建。
_VIEW_INCOMPATIBLE_SQLSTATE = "42P16"

# 重生簽名快取(對齊 datasets:* 快取 key 慣例);TTL 30 天:簽名遺失時最多多重生一次,
# 不影響正確性(view 重生本身冪等)
_SIGNATURE_CACHE_KEY = cache.cache_key("view-generator", "confirmed-signature")
_SIGNATURE_TTL_SECONDS = 60 * 60 * 24 * 30

_SCHEMAS_SQL = text(
    """
    SELECT DISTINCT table_schema
    FROM information_schema.tables
    WHERE table_type = 'BASE TABLE'
      AND table_schema NOT IN ('pg_catalog', 'information_schema', :ds_schema, :semantic_schema)
      AND table_schema NOT LIKE '%\\_en' ESCAPE '\\'
    """
)

_SCHEMA_TABLES_SQL = text(
    """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_type = 'BASE TABLE' AND table_schema = :schema
    """
)

_TABLE_COLUMNS_SQL = text(
    """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = :schema AND table_name = :table
    ORDER BY ordinal_position
    """
)


# ── confirmed 映射讀取 / 分組 / 簽名(純函式,免連線可單元測試)──────────────


async def fetch_confirmed_mapping(session: AsyncSession) -> dict[str, dict[str, str]]:
    """讀本地副本全部 confirmed 映射,依 `table_name` 分組。

    一次查詢取全量,避免逐表查詢(N+1);draft 一律不在回傳結果內。
    """
    stmt = select(
        SemanticMapping.table_name, SemanticMapping.column_name, SemanticMapping.english_name
    ).where(SemanticMapping.status == "confirmed", SemanticMapping.is_deleted.is_(False))
    rows = (await session.execute(stmt)).all()
    return group_confirmed_rows(
        (str(table_name), str(column_name), str(english_name))
        for table_name, column_name, english_name in rows
    )


def group_confirmed_rows(
    rows: Iterable[tuple[str, str, str]],
) -> dict[str, dict[str, str]]:
    """把 `(table_name, column_name, english_name)` 列分組成 `{table: {column: english_name}}`。

    `column_name=''` 為表層級映射(view 名稱依據)。
    """
    grouped: dict[str, dict[str, str]] = {}
    for table_name, column_name, english_name in rows:
        grouped.setdefault(table_name, {})[column_name] = english_name
    return grouped


def compute_confirmed_signature(confirmed: Mapping[str, Mapping[str, str]]) -> str:
    """confirmed 映射內容簽名:排序後正規化字串的 sha256,供偵測「重灌前後差異」。"""
    canonical = "\n".join(
        f"{table}\t{column}\t{english_name}"
        for table in sorted(confirmed)
        for column, english_name in sorted(confirmed[table].items())
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── view SELECT 組裝(純函式)────────────────────────────────────────────


def select_view_columns(
    table_columns: Sequence[str], table_map: Mapping[str, str]
) -> dict[str, str]:
    """表實際欄位 ∩ confirmed 欄位(排除表層級 `''`),依表實際欄位順序回傳 `{欄名: 英文別名}`。"""
    return {
        column: table_map[column]
        for column in table_columns
        if column != "" and column in table_map
    }


def build_view_select_sql(schema: str, table: str, col_aliases: Mapping[str, str]) -> str:
    """組 `SELECT <col> AS <english_name>, ... FROM <schema>.<table>`;識別字全走白名單引號化。"""
    select_list = ", ".join(
        f"{quote_ident(column)} AS {quote_ident(alias)}" for column, alias in col_aliases.items()
    )
    source = f"{quote_ident(schema)}.{quote_ident(table)}"
    return f"SELECT {select_list} FROM {source}"


# ── 目標 RDS 內省(information_schema)────────────────────────────────────


async def _list_target_schemas(conn: AsyncConnection) -> list[str]:
    """列目標 RDS 實際存在的帳套 schema:排除系統 schema / DS / erp_metadata / 自身 `*_en`。"""
    rows = (
        await conn.execute(
            _SCHEMAS_SQL, {"ds_schema": DS_SCHEMA, "semantic_schema": SEMANTIC_SCHEMA}
        )
    ).all()
    return sorted(str(r[0]) for r in rows)


async def _list_schema_tables(conn: AsyncConnection, schema: str) -> list[str]:
    rows = (await conn.execute(_SCHEMA_TABLES_SQL, {"schema": schema})).all()
    return [str(r[0]) for r in rows]


async def _list_table_columns(conn: AsyncConnection, schema: str, table: str) -> list[str]:
    rows = (await conn.execute(_TABLE_COLUMNS_SQL, {"schema": schema, "table": table})).all()
    return [str(r[0]) for r in rows]


def _is_view_incompatible_error(exc: BaseException) -> bool:
    """判斷 REPLACE 失敗是否確認為「既有 view 欄位集合不相容」(Postgres 42P16)。

    僅此情境允許走 DROP VIEW + CREATE 重建;其餘例外(權限不足 / 連線暫時性錯誤等)
    一律回 False,由呼叫端往上拋,不誤觸 DROP(AD-112)。
    """
    if not isinstance(exc, DBAPIError):
        return False
    # asyncpg 例外物件帶 `.sqlstate`(見 asyncpg.exceptions.PostgresError);
    # 經 SQLAlchemy 包裝後原始例外存於 `.orig`。
    sqlstate = getattr(exc.orig, "sqlstate", None)
    return sqlstate == _VIEW_INCOMPATIBLE_SQLSTATE


async def _create_or_replace_view(
    conn: AsyncConnection, qualified_view: str, select_sql: str
) -> None:
    """先嘗試 `CREATE OR REPLACE VIEW`;僅當失敗確認為「欄位集合不相容」(42P16,既有
    view 欄名 / 型別 / 順序不可變更)時,才退回「DROP VIEW IF EXISTS + CREATE VIEW」
    重建流程 — 僅限本情境,且僅 DROP VIEW,不動任何表(對齊 `04-sql-safety.md` 底線,
    不刪表)。其他例外原樣往上拋,交由呼叫端記 warning 並保留原 view(AD-112)。
    """
    try:
        await conn.execute(text(f"CREATE OR REPLACE VIEW {qualified_view} AS {select_sql}"))
    except DBAPIError as exc:
        if not _is_view_incompatible_error(exc):
            raise
        logger.info(
            "CREATE OR REPLACE VIEW 欄位集合不相容(42P16),改走重建流程:%s", qualified_view
        )
        await conn.execute(text(f"DROP VIEW IF EXISTS {qualified_view}"))
        await conn.execute(text(f"CREATE VIEW {qualified_view} AS {select_sql}"))


async def generate_views_for_schema(
    conn: AsyncConnection, schema: str, confirmed: Mapping[str, Mapping[str, str]]
) -> tuple[list[str], list[str]]:
    """對單一帳套 schema:實際存在且有 confirmed 表層級映射的表逐一產生 view。

    回傳 `(建立 / 更新的 view 全名清單, 失敗表清單)`;失敗表清單為 `<schema>.<table>`
    格式(AD-113,供上層決定是否寫入重生簽名)。單表失敗不中斷同 schema 其餘表(對齊
    mirror_sync 單表失敗不中斷整輪的慣例)。
    """
    created: list[str] = []
    failed: list[str] = []
    tables = await _list_schema_tables(conn, schema)
    view_schema: str | None = None
    for table in tables:
        table_map = confirmed.get(table)
        if not table_map:
            continue
        view_name = table_map.get("")
        if not view_name:
            continue  # 無表層級英文名 → 不產生 view
        table_columns = await _list_table_columns(conn, schema, table)
        col_aliases = select_view_columns(table_columns, table_map)
        if not col_aliases:
            continue  # 交集為空 → 跳過該表
        try:
            if view_schema is None:
                view_schema = f"{schema}{VIEW_SCHEMA_SUFFIX}"
                await conn.execute(
                    text(f"CREATE SCHEMA IF NOT EXISTS {quote_ident(view_schema)}")
                )
            qualified_view = f"{quote_ident(view_schema)}.{quote_ident(view_name)}"
            select_sql = build_view_select_sql(schema, table, col_aliases)
            await _create_or_replace_view(conn, qualified_view, select_sql)
            created.append(f"{view_schema}.{view_name}")
        except Exception:
            logger.warning("view 產生失敗,略過該表:%s.%s", schema, table, exc_info=True)
            failed.append(f"{schema}.{table}")
    return created, failed


async def generate_views(
    engine: AsyncEngine, confirmed: Mapping[str, Mapping[str, str]]
) -> tuple[list[str], list[str]]:
    """迴圈目標 RDS 實際存在的帳套 schema,依 confirmed 映射產生語意化 view。

    回傳 `(建立清單, 失敗表清單)`(AD-113)。連線以 AUTOCOMMIT 執行(逐表 DDL 各自即時
    生效):單表失敗不會讓交易中止而波及同一 schema / 其餘 schema 尚未處理的表。
    """
    created: list[str] = []
    failed: list[str] = []
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        schemas = await _list_target_schemas(conn)
        for schema in schemas:
            schema_created, schema_failed = await generate_views_for_schema(
                conn, schema, confirmed
            )
            created.extend(schema_created)
            failed.extend(schema_failed)
    return created, failed


# ── worker 掛點本體(task-003 預留簽名)────────────────────────────────────


async def regenerate_views_if_changed(
    session: AsyncSession, repo: SemanticMappingRepository
) -> None:
    """view 重生本體(task-005):confirmed 映射內容有異動才重生,否則略過。

    `repo` 保留於簽名維持向後相容(task-003 掛點介面);本體改直接以 `session` 一次性
    讀取全量 confirmed 映射(避免逐表查詢 N+1),不透過 `repo.get_confirmed_map`。

    AD-113:僅當本輪全部表皆成功才寫入內容簽名;有表失敗則不更新簽名,讓下輪重生
    (mapping 內容未變動也會)重試補齊缺漏的 view,避免部分失敗被簽名長期抑制重試。
    """
    confirmed = await fetch_confirmed_mapping(session)
    if not confirmed:
        logger.info("尚無 confirmed 映射,略過 view 重生")
        return
    signature = compute_confirmed_signature(confirmed)
    cached = await cache.cache_get(_SIGNATURE_CACHE_KEY)
    if cached == signature:
        logger.info("confirmed 映射內容未異動,略過 view 重生")
        return
    engine = create_async_engine(rds_database_url(RDS_TARGET_DB_ENV))
    try:
        created, failed = await generate_views(engine, confirmed)
    finally:
        await engine.dispose()
    if failed:
        logger.warning(
            "view 重生有 %d 個表失敗,簽名不寫入以便下輪重試:%s", len(failed), failed
        )
    else:
        await cache.cache_set(
            _SIGNATURE_CACHE_KEY, signature, ttl_seconds=_SIGNATURE_TTL_SECONDS
        )
    logger.info("view 重生完成:%d 個 view(失敗 %d 個表)", len(created), len(failed))
