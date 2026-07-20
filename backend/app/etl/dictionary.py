"""DS 字典查詢:對 source RDS 的 ERP 資料字典(GAT_FILE 表名 / GAQ_FILE 欄名 / GAE_FILE 畫面標籤)
取中文描述。

- 表中文名走 `DS.GAT_FILE`,欄中文名走 `DS.GAQ_FILE`;繁體(`'0'`)優先,缺退簡體(`'2'`)。
- 欄中文名查不到時(GAQ 缺漏),退 `DS.GAE_FILE` 畫面欄位標籤補洞(task-006 B1)。
- GAQ04/GAQ05(說明/選項值)有值且不等於中文名時,附加進欄 comment(task-006 B3)。
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
COLUMN_NAME_DICT = "GAQ_FILE"  # GAQ01=欄名 / GAQ02=語別 / GAQ03=中文名 / GAQ04,05=說明/選項
SCREEN_LABEL_DICT = "GAE_FILE"  # GAE01=畫面代碼 / GAE02=欄名(小寫) / GAE03=語別 / GAE04=畫面標籤

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

# 表 ERP 模組代碼:一次批量查多表(繁優先缺退簡;task-007 B2,資料集頁模組分類)
_TABLE_MODULES_BATCH_SQL = text(
    'SELECT lower("GAT01") k, "GAT06" v FROM "DS"."GAT_FILE"'
    ' WHERE lower("GAT01") = ANY(:tables) AND "GAT02" = :lang'
)

# 欄中文名:一次批量查該表所有欄(設計要點 GAQ 查詢,一字不差);併取 GAQ04/05(說明/選項值,B3)
_COLUMN_COMMENT_SQL = text(
    'SELECT lower("GAQ01") k, "GAQ03" v, "GAQ04" v4, "GAQ05" v5 FROM "DS"."GAQ_FILE"'
    ' WHERE lower("GAQ01") = ANY(:cols) AND "GAQ02" = :lang'
)

# 畫面欄位標籤:GAQ 查不到中文名時的 fallback(B1);同一欄可能對應多畫面,
# 依 GAE01 排序取第一筆非空標籤(需求文字明定),故加 ORDER BY(常值欄名,非使用者輸入)
_SCREEN_LABEL_SQL = text(
    'SELECT lower("GAE02") k, "GAE04" v FROM "DS"."GAE_FILE"'
    ' WHERE lower("GAE02") = ANY(:cols) AND "GAE03" = :lang'
    ' ORDER BY "GAE01"'
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


async def fetch_table_modules(
    conn: AsyncConnection, tables: Sequence[str]
) -> dict[str, str]:
    """批量查多表 ERP 模組代碼(GAT06;逐表繁優先缺退簡);回傳 key 為小寫表名。

    語意與 fetch_table_comments 一致(同表 GAT_FILE,取 GAT06 而非 GAT03),
    供 refresh 全量內省批量取用(task-007 B2);字典表缺失、表無對應者靜默略過(不 raise)。
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
                _TABLE_MODULES_BATCH_SQL, {"tables": remaining, "lang": lang}
            )
        ).mappings().all()
        for r in rows:
            value = r["v"]
            if value is not None and str(value).strip():
                result[str(r["k"])] = str(value).strip()
    return result


def _compose_column_comment(name: str, extra1: str | None, extra2: str | None) -> str:
    """組欄 comment:中文名 + GAQ04/05 說明/選項值(去空白後不等於中文名者依序附加,B3)。

    無附加值時原樣回傳中文名,維持現行輸出不變動。
    """
    parts = [name]
    for extra in (extra1, extra2):
        if extra and extra != name:
            parts.append(extra)
    return "；".join(parts)


async def fetch_column_comments(
    conn: AsyncConnection, columns: Sequence[str]
) -> dict[str, str]:
    """批量查該表各欄中文名(逐欄繁優先缺退簡);回傳 key 為小寫欄名。

    - GAQ 有對應:中文名(GAQ03)+ GAQ04/05 說明選項值(不等於中文名者附加,B3)。
    - GAQ 查不到者,退 GAE_FILE 畫面標籤補洞(B1);同一欄多畫面取第一筆非空標籤。
    - 兩字典表皆缺失、欄無對應者靜默略過(不 raise);key 以小寫欄名對映,供呼叫端比對。
    """
    if not columns:
        return {}
    wanted = [c.lower() for c in columns]
    result: dict[str, str] = {}

    if await _dict_table_exists(conn, COLUMN_NAME_DICT):
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
                    name = str(value).strip()
                    v4 = r["v4"]
                    v5 = r["v5"]
                    extra1 = str(v4).strip() if v4 is not None else None
                    extra2 = str(v5).strip() if v5 is not None else None
                    result[str(r["k"])] = _compose_column_comment(name, extra1, extra2)

    # B1:GAQ 仍缺者退 GAE_FILE 畫面標籤;GAE_FILE 表不存在時 graceful 略過(不 raise)
    missing = [c for c in wanted if c not in result]
    if missing and await _dict_table_exists(conn, SCREEN_LABEL_DICT):
        for lang in _LANG_PREFERENCE:
            remaining = [c for c in missing if c not in result]
            if not remaining:
                break
            rows = (
                await conn.execute(_SCREEN_LABEL_SQL, {"cols": remaining, "lang": lang})
            ).mappings().all()
            for r in rows:
                key = str(r["k"])
                if key in result:
                    continue  # 同一欄多畫面已取得第一筆非空標籤,略過後續
                value = r["v"]
                if value is not None and str(value).strip():
                    result[key] = str(value).strip()

    return result
