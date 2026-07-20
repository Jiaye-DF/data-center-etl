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

    - table_exists:{'GAT_FILE': bool, 'GAQ_FILE': bool, 'GAE_FILE': bool} 控字典表是否存在。
    - table_comments:{lang: {lower_table: value}} 表中文名。
    - column_comments:{lang: {lower_col: value}} 欄中文名(GAQ03)。
    - column_extra:{lang: {lower_col: (GAQ04, GAQ05)}} 欄說明/選項值(B3)。
    - screen_labels:{lang: [(lower_col, value), ...]} 畫面標籤(B1),依序模擬 GAE01 排序,
      同一欄可重複出現以測試「取第一筆非空」。
    """

    def __init__(
        self,
        *,
        table_exists: Mapping[str, bool] | None = None,
        table_comments: Mapping[str, Mapping[str, str]] | None = None,
        column_comments: Mapping[str, Mapping[str, str]] | None = None,
        column_extra: Mapping[str, Mapping[str, tuple[str | None, str | None]]] | None = None,
        screen_labels: Mapping[str, Sequence[tuple[str, str | None]]] | None = None,
    ) -> None:
        self._exists = table_exists or {"GAT_FILE": True, "GAQ_FILE": True, "GAE_FILE": True}
        self._table_comments = table_comments or {}
        self._column_comments = column_comments or {}
        self._column_extra = column_extra or {}
        self._screen_labels = screen_labels or {}

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
        if "GAE04" in s:  # 畫面標籤(B1 fallback,依序模擬多畫面)
            lang = str(bound["lang"])
            wanted = set(bound["cols"])
            rows = [
                {"k": k, "v": v}
                for k, v in self._screen_labels.get(lang, [])
                if k in wanted
            ]
            return _FakeResult(rows)
        if "GAQ03" in s:  # 欄中文名(批量,含 GAQ04/05)
            lang = str(bound["lang"])
            wanted = set(bound["cols"])
            src = self._column_comments.get(lang, {})
            extra = self._column_extra.get(lang, {})
            rows = [
                {
                    "k": k,
                    "v": v,
                    "v4": extra.get(k, (None, None))[0],
                    "v5": extra.get(k, (None, None))[1],
                }
                for k, v in src.items()
                if k in wanted
            ]
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


async def test_column_comments_gaq_missing_falls_back_to_gae() -> None:  # B1
    # AAA01 GAQ 有中文名;AAA02 GAQ 兩語別皆無、退 GAE_FILE 畫面標籤補洞
    conn = FakeDictConn(
        column_comments={"0": {"aaa01": "帳別編號"}},
        screen_labels={"0": [("aaa02", "帳別畫面標籤")]},
    )
    result = await fetch_column_comments(conn, ["AAA01", "AAA02"])
    assert result == {"aaa01": "帳別編號", "aaa02": "帳別畫面標籤"}


async def test_column_comments_gae_missing_table_graceful_empty() -> None:  # B1
    # GAQ 查不到、且 GAE_FILE 表未加(DMS 前置未成)時,B1 graceful 略過不 raise
    conn = FakeDictConn(table_exists={"GAT_FILE": True, "GAQ_FILE": True, "GAE_FILE": False})
    assert await fetch_column_comments(conn, ["AAA02"]) == {}


async def test_column_comments_gae_zh_tw_missing_falls_back_to_zh_cn() -> None:  # B1 繁缺退簡
    conn = FakeDictConn(
        screen_labels={"2": [("aaa02", "帐别画面标签")]},
    )
    result = await fetch_column_comments(conn, ["AAA02"])
    assert result == {"aaa02": "帐别画面标签"}


async def test_column_comments_gae_multi_screen_takes_first_non_empty() -> None:  # B1
    # 同一欄對應多畫面,依 GAE01 排序;第一筆為空(None)略過,取第一筆非空標籤
    conn = FakeDictConn(
        screen_labels={
            "0": [("aaa02", None), ("aaa02", "第一個非空標籤"), ("aaa02", "第二個標籤")]
        },
    )
    result = await fetch_column_comments(conn, ["AAA02"])
    assert result == {"aaa02": "第一個非空標籤"}


async def test_column_comments_gaq04_appended_when_differs_from_name() -> None:  # B3
    conn = FakeDictConn(
        column_comments={"0": {"sdf09": "單身多檔註記"}},
        column_extra={"0": {"sdf09": ("1.單檔 2.單檔多欄", None)}},
    )
    result = await fetch_column_comments(conn, ["SDF09"])
    assert result == {"sdf09": "單身多檔註記；1.單檔 2.單檔多欄"}


async def test_column_comments_gaq04_equal_to_name_not_appended() -> None:  # B3
    # GAQ04 與中文名(去空白比對)相同 → 無資訊量,維持現行輸出不附加
    conn = FakeDictConn(
        column_comments={"0": {"aaa01": "帳別編號"}},
        column_extra={"0": {"aaa01": ("帳別編號", None)}},
    )
    result = await fetch_column_comments(conn, ["AAA01"])
    assert result == {"aaa01": "帳別編號"}


async def test_column_comments_gaq04_and_gaq05_both_appended() -> None:  # B3
    conn = FakeDictConn(
        column_comments={"0": {"sdf09": "單身多檔註記"}},
        column_extra={"0": {"sdf09": ("說明文字", "1.單檔 2.單檔多欄")}},
    )
    result = await fetch_column_comments(conn, ["SDF09"])
    assert result == {"sdf09": "單身多檔註記；說明文字；1.單檔 2.單檔多欄"}
