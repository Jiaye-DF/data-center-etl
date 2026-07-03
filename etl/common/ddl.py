"""純函式 DDL 產生器:欄位 Comment 語句組裝與識別字 / 字串常值跳脫。

不依賴 Spark session,方便單元測試(見 tests/test_ddl.py)。
SQL 安全對齊 docs/Design-Base/04-databases/04-sql-safety.md、01-identifiers.md:
DDL 的識別字與 COMMENT 字串常值無法用 bind params,故一律以下列 helper 跳脫,禁裸字串拼接。
"""

from __future__ import annotations

import re

# PostgreSQL 合法(未加引號)識別字:字母 / 底線開頭,後接字母 / 數字 / 底線 / 錢號。
# 這裡僅用於「基本合法性」把關(擋控制字元、空字串、含引號注入等);實際輸出一律加雙引號。
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def quote_ident(name: str) -> str:
    """把識別字(schema / table / column)以 PostgreSQL 雙引號安全引號化。

    規則:內部 `"` 跳脫為 `""`,外層包一對雙引號。
    先驗基本合法性,擋空字串 / 含 NUL 或換行等控制字元的識別字。
    """
    if not isinstance(name, str) or name == "":
        raise ValueError(f"識別字不可為空:{name!r}")
    if "\x00" in name or "\n" in name or "\r" in name:
        raise ValueError(f"識別字含非法控制字元:{name!r}")
    return '"' + name.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    """把字串常值(COMMENT 內容)以單引號安全引號化:內部 `'` 跳脫為 `''`。"""
    if value is None:
        raise ValueError("字串常值不可為 None")
    return "'" + str(value).replace("'", "''") + "'"


def build_column_comments(
    table: str,
    columns: list[str],
    comments: dict[str, str],
    *,
    schema: str = "public",
) -> list[str]:
    """為 `columns` 中的**每一欄位**產生一條 `COMMENT ON COLUMN` 語句。

    契約:
      - `columns` 為該表的完整欄位清單;函式保證輸出條數 == len(columns)(N 欄 → N 條)。
      - `comments` 為 {欄名: 描述} 對照;**每一欄位都必須有描述**。
        若 `columns` 中有欄位在 `comments` 缺席(或描述為空字串)→ raise ValueError,
        訊息列出所有缺描述的欄名(不靜默略過)。
      - 識別字("schema"."table"."col")以雙引號跳脫;描述以單引號跳脫,禁注入。

    回傳:list[str],每條形如
      COMMENT ON COLUMN "schema"."table"."col" IS '描述';
    """
    missing = [
        col
        for col in columns
        if col not in comments or comments[col] is None or str(comments[col]).strip() == ""
    ]
    if missing:
        raise ValueError(f"下列欄位缺 comment 描述:{missing}")

    stmts: list[str] = []
    for col in columns:
        target = f"{quote_ident(schema)}.{quote_ident(table)}.{quote_ident(col)}"
        stmts.append(f"COMMENT ON COLUMN {target} IS {quote_literal(comments[col])};")
    return stmts
