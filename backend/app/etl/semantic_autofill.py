"""語意映射自動補列(v1.5.2 task-002,propose 「語意映射自動補列」)。

同步收尾時比對目標 RDS 帳套 schema 實體欄位 vs `erp_metadata.semantic_mappings`
既有列,缺列自動補 `status='confirmed'`,讓來源新增欄位(與缺表層級列的表)於同輪
即進語意 view 與 JSON 查詢。純模組 + 測試,本 task 不掛同步流程(掛接為 task-003)。

補列規則(**既有列不論 draft / confirmed 一律不覆寫**):
- 欄層級缺列 → 補 `english_name=原始欄名小寫`、`zh_name=DS 字典中文名(缺則空字串)`、
  `updated_by=系統全零 UUID`、`status='confirmed'`;`zh_name` 重用
  `app/etl/dictionary.py` `fetch_column_comments`(經來源連線取字典,取不到留空)。
- 表層級列(`column_name=''`)缺 → 一併補,`english_name=原始表名小寫`(否則 view 整表不產生)。
- 別名查重(同表內):自動英文名撞同表既有 `english_name`(含本輪擬插入者)→ 確定性規避:
  改用 `<欄名小寫>_col`,仍撞則附遞增序號 `_col2`、`_col3`…,避免 view 因 SELECT 別名
  重複而建不起來。

冪等 / 併發安全:寫入用 `INSERT ... ON CONFLICT (table_name, column_name) DO NOTHING`
(值一律 bind params,識別字為白名單常值);多 worker 同時執行不炸 PK。

連線慣例:目標 RDS 走 `AWS_RDS_TARGET_DB`(內省帳套 schema + 讀既有映射 + 寫入);
DS 字典走來源連線(`AWS_RDS_SOURCE_DB`,對齊 `mirror.mirror_table` 取字典的連線)。
schema 排除 / information_schema 內省慣例沿用 `view_generator.py`(排 DS / erp_metadata /
`*_view` / `*_en`);識別字白名單常值,對齊 `docs/Design-Base/04-databases/04-sql-safety.md`。
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.etl.comments import quote_ident
from app.etl.dictionary import fetch_column_comments
from app.etl.mirror import DS_SCHEMA
from app.etl.semantic_schema import SEMANTIC_SCHEMA, SEMANTIC_TABLE

logger = logging.getLogger(__name__)

# 語意層目標表全名(白名單常值,對齊 seed_semantic_mappings 慣例)
_QUALIFIED = f"{quote_ident(SEMANTIC_SCHEMA)}.{quote_ident(SEMANTIC_TABLE)}"

# 系統帳號全零 UUID(user 決議 2026-07-21:自動列 updated_by 一律填全零,供人工辨識系統列)
_ZERO_UUID = UUID("00000000-0000-0000-0000-000000000000")

# 別名規避後綴:自動英文名撞既有 → `<base>_col`,仍撞附序號 `_col2`、`_col3`…
_ALIAS_SUFFIX = "_col"

# 目標 RDS 內省:帳套 schema 各 base table 的 (table_name, column_name)。
# schema 排除慣例沿用 view_generator.py(排系統 schema / DS / erp_metadata / `*_view` / 舊制 `*_en`);
# 跨帳套同名主檔(propose A4:GEM/GEN/ABM 集中託管、M2201/S2202 synonym)自然依 table_name 收斂。
_TARGET_COLUMNS_SQL = text(
    """
    SELECT c.table_name, c.column_name
    FROM information_schema.columns c
    JOIN information_schema.tables t
      ON t.table_schema = c.table_schema AND t.table_name = c.table_name
    WHERE t.table_type = 'BASE TABLE'
      AND c.table_schema NOT IN ('pg_catalog', 'information_schema', :ds_schema, :semantic_schema)
      AND c.table_schema NOT LIKE '%\\_view' ESCAPE '\\'
      AND c.table_schema NOT LIKE '%\\_en' ESCAPE '\\'
    ORDER BY c.table_name, c.ordinal_position
    """
)

# 既有映射一次全撈記憶體比對(禁逐欄查詢 N+1);english_name 供同表別名查重
_SELECT_EXISTING_SQL = text(
    f"SELECT table_name, column_name, english_name FROM {_QUALIFIED}"
)

# 缺列補 confirmed:值全 bind params,status 為白名單常值;updated_at 由 DEFAULT
# (now() AT TIME ZONE 'Asia/Taipei')落地 UTC+8 naive,不另傳。ON CONFLICT 保冪等 / 併發安全。
_INSERT_SQL = text(
    f"""
    INSERT INTO {_QUALIFIED}
        (table_name, column_name, english_name, zh_name, status, updated_by)
    VALUES (:t, :c, :e, :z, 'confirmed', :u)
    ON CONFLICT (table_name, column_name) DO NOTHING
    """
)


@dataclass(frozen=True)
class AutofillResult:
    """自動補列結果統計(供掛接端 log)。"""

    columns_added: int = 0  # 補欄層級列數
    tables_added: int = 0  # 補表層級列數
    aliases_deduped: int = 0  # 同表別名撞名規避次數


def _resolve_alias(base: str, taken: set[str]) -> tuple[str, bool]:
    """自動英文別名確定性規避:`base` 未撞則原樣;撞則 `base_col`、`base_col2`、`base_col3`…

    回傳 `(最終別名, 是否發生規避)`;僅比對 `taken`(同表既有 + 本輪已配發別名)。
    """
    if base not in taken:
        return base, False
    candidate = f"{base}{_ALIAS_SUFFIX}"
    n = 2
    while candidate in taken:
        candidate = f"{base}{_ALIAS_SUFFIX}{n}"
        n += 1
    return candidate, True


def plan_autofill(
    target_tables: Mapping[str, Sequence[str]],
    existing: Iterable[tuple[str, str, str]],
    zh_lookup: Mapping[str, str],
) -> tuple[list[dict[str, object]], AutofillResult]:
    """純函式規劃:算出缺列的 INSERT 參數與統計(免連線,便於單元測試)。

    - `target_tables`:目標 RDS 帳套實體 `{表名: [原始欄名, ...]}`(跨 schema 已收斂)。
    - `existing`:既有映射 `(table_name, column_name, english_name)`;既有鍵一律略過(不覆寫)。
    - `zh_lookup`:小寫欄名 → DS 字典中文名(缺則欄位補空字串)。

    別名查重以「同表既有 english_name(含表層級) + 本輪已配發」為 `taken` 集合,確定性規避。
    表名 / 欄名一律取小寫作 english_name(對齊 v1.5.1 unused 命名決議)。
    """
    existing_keys: set[tuple[str, str]] = set()
    existing_english: dict[str, set[str]] = {}
    for table_name, column_name, english_name in existing:
        existing_keys.add((table_name, column_name))
        existing_english.setdefault(table_name, set()).add(english_name)

    inserts: list[dict[str, object]] = []
    columns_added = 0
    tables_added = 0
    aliases_deduped = 0

    for table_name in sorted(target_tables):
        taken = set(existing_english.get(table_name, set()))

        # 表層級缺列 → 補表名小寫(view 名依據;無此列 view 整表不產生)
        if (table_name, "") not in existing_keys:
            table_english = table_name.lower()
            inserts.append(
                {"t": table_name, "c": "", "e": table_english, "z": "", "u": _ZERO_UUID}
            )
            taken.add(table_english)
            tables_added += 1

        # 欄層級缺列 → 補小寫欄名(別名查重規避)+ DS 字典中文名(缺則空)
        for column_name in sorted(target_tables[table_name]):
            if column_name == "" or (table_name, column_name) in existing_keys:
                continue
            base = column_name.lower()
            alias, deduped = _resolve_alias(base, taken)
            if deduped:
                aliases_deduped += 1
            taken.add(alias)
            inserts.append(
                {
                    "t": table_name,
                    "c": column_name,
                    "e": alias,
                    "z": zh_lookup.get(base, ""),
                    "u": _ZERO_UUID,
                }
            )
            columns_added += 1

    return inserts, AutofillResult(
        columns_added=columns_added,
        tables_added=tables_added,
        aliases_deduped=aliases_deduped,
    )


async def _introspect_target_tables(conn: AsyncConnection) -> dict[str, list[str]]:
    """內省目標帳套 schema 實體表 → `{表名: [原始欄名, ...]}`(跨 schema 依 table_name 收斂)。"""
    rows = (
        await conn.execute(
            _TARGET_COLUMNS_SQL, {"ds_schema": DS_SCHEMA, "semantic_schema": SEMANTIC_SCHEMA}
        )
    ).all()
    tables: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        t, c = str(table_name), str(column_name)
        bucket = seen.setdefault(t, set())
        if c not in bucket:
            bucket.add(c)
            tables.setdefault(t, []).append(c)
    return tables


async def _fetch_existing_mappings(conn: AsyncConnection) -> list[tuple[str, str, str]]:
    """一次全撈既有映射列 `(table_name, column_name, english_name)`;記憶體比對,禁 N+1。"""
    rows = (await conn.execute(_SELECT_EXISTING_SQL)).all()
    return [(str(r[0]), str(r[1]), str(r[2])) for r in rows]


async def autofill_semantic_mappings(
    target_engine: AsyncEngine,
    source_engine: AsyncEngine,
    scope_tables: Collection[str] | None = None,
) -> AutofillResult:
    """對外入口(task-003 掛接 mirror_sync 收尾用)。

    流程:目標 RDS 內省帳套實體欄位 + 一次全撈既有映射 → 算缺列 → 來源連線批量取 DS 字典
    中文名(僅缺列欄位,避免 N+1)→ 目標 RDS 以 `INSERT ... ON CONFLICT DO NOTHING` 補列。
    回傳補列統計。無缺列時不開寫入交易。

    `scope_tables`(AD-145):本輪同步的表名集合(mirror 目標表名 = 來源表名,原樣比對);
    給定時內省結果僅保留集合內的表,將補列面圈定為本輪處理範圍;None 維持現行全庫掃描
    (向後相容,既有直呼測試不受影響)。
    """
    async with target_engine.connect() as conn:
        target_tables = await _introspect_target_tables(conn)
        existing = await _fetch_existing_mappings(conn)

    if scope_tables is not None:
        wanted = set(scope_tables)
        target_tables = {t: cols for t, cols in target_tables.items() if t in wanted}

    existing_keys = {(t, c) for t, c, _ in existing}
    missing_columns = sorted(
        {
            column
            for table, columns in target_tables.items()
            for column in columns
            if column != "" and (table, column) not in existing_keys
        }
    )

    # AD-144:autofill 的 zh_name 只取純中文名(GAQ03 / GAE fallback),
    # 絕不串接 GAQ04/05 說明選項值(COMMENT 路徑不受影響)
    zh_lookup: dict[str, str] = {}
    if missing_columns:
        async with source_engine.connect() as source_conn:
            zh_lookup = await fetch_column_comments(
                source_conn, missing_columns, include_extras=False
            )

    inserts, result = plan_autofill(target_tables, existing, zh_lookup)
    if inserts:
        async with target_engine.begin() as conn:
            await conn.execute(_INSERT_SQL, inserts)

    logger.info(
        "語意映射自動補列完成:補欄 %d / 補表層級 %d / 別名規避 %d",
        result.columns_added,
        result.tables_added,
        result.aliases_deduped,
    )
    # AD-145:本輪實際補列的表名清單 log info(供人審)
    if inserts:
        touched = sorted({str(p["t"]) for p in inserts})
        logger.info("語意映射自動補列表清單(本輪實際補列):%s", ", ".join(touched))
    return result
