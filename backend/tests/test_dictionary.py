"""dictionary 字典查詢測試:以 fake AsyncConnection 驗繁優先缺退簡、字典表缺失回空不 raise。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.etl.dictionary import fetch_column_comments, fetch_table_comment


class _FakeResult:
    """對照 SQLAlchemy Result 的最小子集:first() / mappings().all()。"""

    def __init__(self, rows: Sequence[Any]) -> None:
        self._rows = list(rows)

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None

    def mappings(self) -> _FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


class FakeDictConn:
    """依 SQL 內容與 bind params 回傳預置列。

    - table_exists:{'GAT_FILE': bool, 'GAQ_FILE': bool} 控字典表是否存在。
    - table_comments:{lang: {lower_table: value}} 表中文名。
    - column_comments:{lang: {lower_col: value}} 欄中文名。
    """

    def __init__(
        self,
        *,
        table_exists: Mapping[str, bool] | None = None,
        table_comments: Mapping[str, Mapping[str, str]] | None = None,
        column_comments: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        self._exists = table_exists or {"GAT_FILE": True, "GAQ_FILE": True}
        self._table_comments = table_comments or {}
        self._column_comments = column_comments or {}

    async def execute(
        self, sql: Any, params: Mapping[str, Any] | None = None
    ) -> _FakeResult:
        s = str(sql)
        bound = dict(params or {})
        if "information_schema.tables" in s:
            name = str(bound["t"])
            return _FakeResult([(1,)] if self._exists.get(name, False) else [])
        if "GAT03" in s:  # 表中文名
            lang = str(bound["lang"])
            key = str(bound["t"])
            value = self._table_comments.get(lang, {}).get(key)
            return _FakeResult([(value,)] if value is not None else [])
        if "GAQ03" in s:  # 欄中文名(批量)
            lang = str(bound["lang"])
            wanted = set(bound["cols"])
            src = self._column_comments.get(lang, {})
            rows = [{"k": k, "v": v} for k, v in src.items() if k in wanted]
            return _FakeResult(rows)
        raise AssertionError(f"未預期 SQL:{s}")


async def test_table_comment_prefers_zh_tw() -> None:
    conn = FakeDictConn(
        table_comments={"0": {"aaa_file": "帳別參數檔"}, "2": {"aaa_file": "账别参数档"}}
    )
    assert await fetch_table_comment(conn, "AAA_FILE") == "帳別參數檔"


async def test_table_comment_falls_back_to_zh_cn() -> None:
    conn = FakeDictConn(table_comments={"2": {"aaa_file": "账别参数档"}})
    assert await fetch_table_comment(conn, "AAA_FILE") == "账别参数档"


async def test_table_comment_missing_dict_returns_none_no_raise() -> None:
    conn = FakeDictConn(table_exists={"GAT_FILE": False, "GAQ_FILE": False})
    assert await fetch_table_comment(conn, "AAA_FILE") is None


async def test_table_comment_no_match_returns_none() -> None:
    conn = FakeDictConn(table_comments={"0": {"bbb_file": "他表"}})
    assert await fetch_table_comment(conn, "AAA_FILE") is None


async def test_column_comments_zh_priority_with_per_column_fallback() -> None:
    # AAA01 繁體有值(優先);AAA02 繁體缺、簡體有值(退簡);AAA03 兩者皆無(略過)
    conn = FakeDictConn(
        column_comments={
            "0": {"aaa01": "帳別編號"},
            "2": {"aaa01": "账别编号", "aaa02": "名称"},
        }
    )
    result = await fetch_column_comments(conn, ["AAA01", "AAA02", "AAA03"])
    assert result == {"aaa01": "帳別編號", "aaa02": "名称"}


async def test_column_comments_missing_dict_returns_empty_no_raise() -> None:
    conn = FakeDictConn(table_exists={"GAT_FILE": True, "GAQ_FILE": False})
    assert await fetch_column_comments(conn, ["AAA01", "AAA02"]) == {}


async def test_column_comments_empty_columns_returns_empty() -> None:
    conn = FakeDictConn()
    assert await fetch_column_comments(conn, []) == {}
