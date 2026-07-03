"""COMMENT ON COLUMN 語句組裝與識別字 / 字串常值跳脫(移植 v1.0.0 `etl/common/ddl.py`)。

SQL 安全對齊 `docs/Design-Base/04-databases/04-sql-safety.md`:
DDL 的識別字與 COMMENT 字串常值無法用 bind params,故識別字一律走白名單驗證 + 雙引號引號化,
字串常值走單引號跳脫,禁裸字串拼接。
"""

from __future__ import annotations

import re

# PostgreSQL 識別字白名單:字母 / 底線開頭,後接字母 / 數字 / 底線 / 錢號。
# 識別字(schema / table / column)一律須通過本白名單,擋注入與控制字元。
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def quote_ident(name: str) -> str:
    """識別字(schema / table / column)通過白名單驗證後以雙引號引號化。

    不符白名單(空字串 / 含空白 / 含引號或分號等)一律 raise,不靜默修補。
    """
    if not isinstance(name, str) or not _IDENT_RE.fullmatch(name):
        raise ValueError(f"識別字不合法:{name!r}")
    return f'"{name}"'


def quote_literal(value: str) -> str:
    """把字串常值(COMMENT 內容)以單引號安全引號化:內部 `'` 跳脫為 `''`。"""
    return "'" + value.replace("'", "''") + "'"


def build_column_comments(
    table: str,
    columns: list[str],
    comments: dict[str, str],
    *,
    schema: str = "public",
) -> list[str]:
    """為 `columns` 中的**每一欄位**產生一條 `COMMENT ON COLUMN` 語句。

    契約(與 v1.0.0 `etl/common/ddl.py` 一致):
      - `columns` 為該表的完整欄位清單;保證輸出條數 == len(columns)(N 欄 → N 條)。
      - 每一欄位都必須有非空描述;缺席或空字串 → raise ValueError,
        訊息列出所有缺描述的欄名(不靜默略過)。
      - 識別字以白名單 + 雙引號跳脫;描述以單引號跳脫,禁注入。
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
