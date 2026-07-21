"""mirror 鏡像引擎測試:DS 排序最前、型別重建、TRUNCATE 不 DROP、分批不整表物化、comment 放寬。

以 fake AsyncConnection 記錄實際執行的 SQL 斷言,不連真 RDS。
"""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.etl.mirror import (
    MirrorColumn,
    build_comment_statements,
    sort_source_tables,
    source_type_to_ddl,
    write_mirror,
)


class _FakeResult:
    def __init__(self, rows: Sequence[Any]) -> None:
        self._rows = list(rows)

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None


class FakeConn:
    """記錄所有執行的 SQL 文字;可設定目標表是否已存在(供 TRUNCATE / CREATE 分流)。"""

    def __init__(self, *, table_exists: bool) -> None:
        self._table_exists = table_exists
        self.executed: list[str] = []
        self.driver_executed: list[str] = []
        self.insert_batches: list[int] = []

    async def execute(self, sql: Any, params: Any = None) -> _FakeResult:
        s = str(sql)
        self.executed.append(s)
        if "INSERT INTO" in s and isinstance(params, list):
            self.insert_batches.append(len(params))
        if "information_schema.tables" in s:
            return _FakeResult([(1,)] if self._table_exists else [])
        return _FakeResult([])

    async def exec_driver_sql(self, sql: str) -> _FakeResult:
        self.executed.append(sql)
        self.driver_executed.append(sql)
        return _FakeResult([])

    def begin_nested(self) -> _FakeSavepoint:
        return _FakeSavepoint()


class _FakeSavepoint:
    """對齊 AsyncConnection.begin_nested 的 async context manager 介面(SAVEPOINT no-op)。"""

    async def __aenter__(self) -> _FakeSavepoint:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


async def _make_batches(
    batches: Sequence[Sequence[Mapping[str, Any]]],
) -> Any:
    for b in batches:
        yield b


# ---------------------------------------------------------------------------
# list_source_tables 排序:DS 最前
# ---------------------------------------------------------------------------


def test_sort_source_tables_ds_first() -> None:
    rows = [
        {"schema": "M2201", "name": "M2201"},
        {"schema": "DS", "name": "GAQ_FILE"},
        {"schema": "APP", "name": "ZZZ"},
        {"schema": "DS", "name": "AAA_FILE"},
    ]
    result = sort_source_tables(rows)
    # DS 全數排最前(內部依名),其餘依 schema / 名
    assert result == [
        ("DS", "AAA_FILE"),
        ("DS", "GAQ_FILE"),
        ("APP", "ZZZ"),
        ("M2201", "M2201"),
    ]


# ---------------------------------------------------------------------------
# 型別重建:保留 varchar 長度 / numeric precision,scale;未知落 TEXT
# ---------------------------------------------------------------------------


def test_source_type_to_ddl_preserves_length_and_precision() -> None:
    def row(**kw: Any) -> dict[str, Any]:
        base = {
            "data_type": "",
            "character_maximum_length": None,
            "numeric_precision": None,
            "numeric_scale": None,
        }
        base.update(kw)
        return base

    varchar = row(data_type="character varying", character_maximum_length=10)
    char = row(data_type="character", character_maximum_length=4)
    numeric = row(data_type="numeric", numeric_precision=15, numeric_scale=2)
    numeric_p = row(data_type="numeric", numeric_precision=8)
    assert source_type_to_ddl(varchar) == "VARCHAR(10)"
    assert source_type_to_ddl(char) == "CHAR(4)"
    assert source_type_to_ddl(numeric) == "NUMERIC(15,2)"
    assert source_type_to_ddl(numeric_p) == "NUMERIC(8)"
    assert source_type_to_ddl(row(data_type="integer")) == "INTEGER"
    assert source_type_to_ddl(row(data_type="bigint")) == "BIGINT"
    assert source_type_to_ddl(row(data_type="timestamp without time zone")) == "TIMESTAMP"
    # 時間型別通則(2026-07-20):帶時區來源一律正規化為 naive(datetime2 等價)
    assert source_type_to_ddl(row(data_type="timestamp with time zone")) == "TIMESTAMP"
    assert source_type_to_ddl(row(data_type="time with time zone")) == "TIME"
    assert source_type_to_ddl(row(data_type="date")) == "DATE"
    # 未知型別保守落 TEXT(不 raise)
    assert source_type_to_ddl(row(data_type="some_exotic_type")) == "TEXT"


# ---------------------------------------------------------------------------
# comment 放寬:無對應欄略過、不 raise
# ---------------------------------------------------------------------------


def test_build_comment_statements_skips_missing_no_raise() -> None:
    stmts = build_comment_statements(
        "DS",
        "AAA_FILE",
        ["AAA01", "AAA02", "AAA03"],
        table_comment="帳別參數檔",
        column_comments={"aaa01": "帳別編號"},  # AAA02 / AAA03 無對應 → 略過
    )
    assert '''COMMENT ON TABLE "DS"."AAA_FILE" IS '帳別參數檔';''' in stmts
    assert '''COMMENT ON COLUMN "DS"."AAA_FILE"."AAA01" IS '帳別編號';''' in stmts
    # 無對應欄不產生 COMMENT、不 raise
    assert len(stmts) == 2


def test_build_comment_statements_no_table_comment() -> None:
    stmts = build_comment_statements(
        "DS", "AAA_FILE", ["AAA01"], table_comment=None, column_comments={}
    )
    assert stmts == []


# ---------------------------------------------------------------------------
# write_mirror:表存在 → TRUNCATE(禁 DROP);不存在 → CREATE TABLE 保留型別
# ---------------------------------------------------------------------------


async def test_write_mirror_existing_table_truncates_not_drops() -> None:
    conn = FakeConn(table_exists=True)
    columns = [MirrorColumn("AAA01", "VARCHAR(10)"), MirrorColumn("AAA02", "VARCHAR(20)")]
    written = await write_mirror(
        conn,
        schema="DS",
        table="AAA_FILE",
        columns=columns,
        row_batches=_make_batches([[{"AAA01": "1", "AAA02": "x"}]]),
        table_comment="帳別參數檔",
        column_comments={"aaa01": "帳別編號"},
    )
    joined = "\n".join(conn.executed)
    assert written == 1
    assert "TRUNCATE TABLE" in joined
    assert "CREATE TABLE" not in joined
    # 禁 DROP:任何情況不得出現 DROP
    assert "DROP" not in joined.upper()


async def test_write_mirror_missing_table_creates_with_real_types() -> None:
    conn = FakeConn(table_exists=False)
    columns = [MirrorColumn("AAA01", "VARCHAR(10)"), MirrorColumn("AAA02", "NUMERIC(15,2)")]
    await write_mirror(
        conn,
        schema="DS",
        table="AAA_FILE",
        columns=columns,
        row_batches=_make_batches([[{"AAA01": "1", "AAA02": "2"}]]),
        table_comment=None,
        column_comments={},
    )
    joined = "\n".join(conn.executed)
    assert 'CREATE TABLE "DS"."AAA_FILE"' in joined
    assert '"AAA01" VARCHAR(10)' in joined
    assert '"AAA02" NUMERIC(15,2)' in joined
    assert "TRUNCATE" not in joined
    assert "DROP" not in joined.upper()


async def test_write_mirror_streams_in_batches_not_materialized() -> None:
    """分批 INSERT:每批各一次 execute,不整表物化(scan AD-006)。"""
    conn = FakeConn(table_exists=True)
    columns = [MirrorColumn("AAA01", "VARCHAR(10)")]
    batches = [
        [{"AAA01": "a"}, {"AAA01": "b"}],
        [{"AAA01": "c"}],
    ]
    written = await write_mirror(
        conn,
        schema="DS",
        table="AAA_FILE",
        columns=columns,
        row_batches=_make_batches(batches),
        table_comment=None,
        column_comments={},
    )
    assert written == 3
    # 兩批 → 兩次 INSERT execute,批量 params 各為 2 / 1(逐批,非一次全塞)
    assert conn.insert_batches == [2, 1]


async def test_write_mirror_comment_with_colon_goes_driver_raw() -> None:
    """COMMENT 內容含冒號(如 "Y":1)須以 driver 直送執行,不得經 text() 誤解析成 bind 參數。"""
    conn = FakeConn(table_exists=True)
    columns = [MirrorColumn("AZA72", "VARCHAR(1)")]
    await write_mirror(
        conn,
        schema="DS",
        table="AZA_FILE",
        columns=columns,
        row_batches=_make_batches([[{"AZA72": "Y"}]]),
        table_comment=None,
        column_comments={"aza72": '是否與EasyFlowGP整合("Y":1, "N":2)'},
    )
    # COMMENT 語句必須走 exec_driver_sql,且冒號內容原樣保留
    assert any('("Y":1, "N":2)' in s for s in conn.driver_executed)


async def test_write_mirror_skips_empty_batches() -> None:
    conn = FakeConn(table_exists=True)
    columns = [MirrorColumn("AAA01", "VARCHAR(10)")]
    written = await write_mirror(
        conn,
        schema="DS",
        table="AAA_FILE",
        columns=columns,
        row_batches=_make_batches([[], [{"AAA01": "a"}], []]),
        table_comment=None,
        column_comments={},
    )
    assert written == 1
    assert conn.insert_batches == [1]


class _SchemaRaceConn(FakeConn):
    """模擬併發搶建 schema 輸掉:CREATE SCHEMA 一律撞 pg_namespace 唯一索引。"""

    async def execute(self, sql: Any, params: Any = None) -> _FakeResult:
        s = str(sql)
        if "CREATE SCHEMA" in s:
            self.executed.append(s)
            raise IntegrityError(s, params, Exception("duplicate key pg_namespace_nspname_index"))
        return await super().execute(sql, params)


async def test_write_mirror_swallows_schema_create_race() -> None:
    """多表並行首次同步同 schema:搶建輸掉(IntegrityError)須吞掉續行,不中止鏡像。"""
    conn = _SchemaRaceConn(table_exists=True)
    columns = [MirrorColumn("AAA01", "VARCHAR(10)")]
    written = await write_mirror(
        conn,
        schema="G2203",
        table="AAA_FILE",
        columns=columns,
        row_batches=_make_batches([[{"AAA01": "a"}]]),
        table_comment=None,
        column_comments={},
    )
    assert written == 1
    joined = "\n".join(conn.executed)
    assert "TRUNCATE TABLE" in joined
