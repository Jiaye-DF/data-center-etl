"""DS 字典查詢:對 source RDS 的 ERP 資料字典(GAT_FILE 表名 / GAQ_FILE 欄名)取中文描述。

- 表中文名走 `DS.GAT_FILE`,欄中文名走 `DS.GAQ_FILE`;繁體(`'0'`)優先,缺退簡體(`'2'`)。
- 識別字為白名單常值(schema / table / column 皆硬編於 SQL,非使用者輸入),
  查詢值一律 bind params(`04-sql-safety.md`)。
- 字典表缺失時 graceful 回空(不 raise)——comment 放寬(task-003 In Scope ⑦)。
- 連線由呼叫端(mirror)提供;本模組不建連線、不 log 機密。
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# 字典表所在 schema 與表名(ERP 資料字典)
DICT_SCHEMA = "DS"
TABLE_NAME_DICT = "GAT_FILE"  # GAT01=表名 / GAT02=語別 / GAT03=中文名
COLUMN_NAME_DICT = "GAQ_FILE"  # GAQ01=欄名 / GAQ02=語別 / GAQ03=中文名

# 語別代碼:繁體優先,缺退簡體
LANG_ZH_TW = "0"
LANG_ZH_CN = "2"
_LANG_PREFERENCE = (LANG_ZH_TW, LANG_ZH_CN)

_DICT_TABLE_EXISTS_SQL = text(
    "SELECT 1 FROM information_schema.tables"
    " WHERE table_schema = :s AND table_name = :t"
)

# 表中文名:繁優先缺退簡(設計要點 GAT 查詢,一字不差)
_TABLE_COMMENT_SQL = text(
    'SELECT "GAT03" FROM "DS"."GAT_FILE" WHERE lower("GAT01") = :t AND "GAT02" = :lang'
)

# 表中文名:一次批量查多表(繁優先缺退簡);避免 refresh 全量內省逐表 N 次 RDS 來回
_TABLE_COMMENTS_BATCH_SQL = text(
    'SELECT lower("GAT01") k, "GAT03" v FROM "DS"."GAT_FILE"'
    ' WHERE lower("GAT01") = ANY(:tables) AND "GAT02" = :lang'
)

# 欄中文名:一次批量查該表所有欄(設計要點 GAQ 查詢,一字不差)
_COLUMN_COMMENT_SQL = text(
    'SELECT lower("GAQ01") k, "GAQ03" v FROM "DS"."GAQ_FILE"'
    ' WHERE lower("GAQ01") = ANY(:cols) AND "GAQ02" = :lang'
)


async def _dict_table_exists(conn: AsyncConnection, table_name: str) -> bool:
    """字典表是否存在;缺失時上層 graceful 回空(不 raise)。"""
    row = (
        await conn.execute(_DICT_TABLE_EXISTS_SQL, {"s": DICT_SCHEMA, "t": table_name})
    ).first()
    return row is not None


async def fetch_table_comment(conn: AsyncConnection, table: str) -> str | None:
    """查表中文名(繁優先缺退簡);字典表缺失或無對應回 None(不 raise)。"""
    if not await _dict_table_exists(conn, TABLE_NAME_DICT):
        return None
    key = table.lower()
    for lang in _LANG_PREFERENCE:
        row = (await conn.execute(_TABLE_COMMENT_SQL, {"t": key, "lang": lang})).first()
        if row is not None and row[0] is not None and str(row[0]).strip():
            return str(row[0]).strip()
    return None


async def fetch_table_comments(
    conn: AsyncConnection, tables: Sequence[str]
) -> dict[str, str]:
    """批量查多表中文名(逐表繁優先缺退簡);回傳 key 為小寫表名。

    取代 fetch_table_comment 的逐表查詢(N 表 = N 次 RDS 來回),供 refresh 全量內省用;
    字典表缺失、表無對應者靜默略過(不 raise)。
    """
    if not tables or not await _dict_table_exists(conn, TABLE_NAME_DICT):
        return {}
    wanted = [t.lower() for t in tables]
    result: dict[str, str] = {}
    for lang in _LANG_PREFERENCE:
        remaining = [t for t in wanted if t not in result]
        if not remaining:
            break
        rows = (
            await conn.execute(
                _TABLE_COMMENTS_BATCH_SQL, {"tables": remaining, "lang": lang}
            )
        ).mappings().all()
        for r in rows:
            value = r["v"]
            if value is not None and str(value).strip():
                result[str(r["k"])] = str(value).strip()
    return result


async def fetch_column_comments(
    conn: AsyncConnection, columns: Sequence[str]
) -> dict[str, str]:
    """批量查該表各欄中文名(逐欄繁優先缺退簡);回傳 key 為小寫欄名。

    字典表缺失、欄無對應者靜默略過(不 raise);key 以小寫欄名對映,供呼叫端比對。
    """
    if not columns or not await _dict_table_exists(conn, COLUMN_NAME_DICT):
        return {}
    wanted = [c.lower() for c in columns]
    result: dict[str, str] = {}
    for lang in _LANG_PREFERENCE:
        remaining = [c for c in wanted if c not in result]
        if not remaining:
            break
        rows = (
            await conn.execute(_COLUMN_COMMENT_SQL, {"cols": remaining, "lang": lang})
        ).mappings().all()
        for r in rows:
            value = r["v"]
            if value is not None and str(value).strip():
                result[str(r["k"])] = str(value).strip()
    return result
