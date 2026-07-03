"""reader 純函式單元測試:識別字組裝與 JDBC URL,不需真連 DB。

pytest 自 etl/ 目錄執行,故以 common.reader 匯入。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 確保 etl/ 在 sys.path(不論從 etl/ 或 repo 根執行皆可 import common.reader)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.reader import (  # noqa: E402
    build_jdbc_url,
    qualified_table,
    quote_identifier,
)


def test_build_jdbc_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DB_HOST", "db.internal")
    monkeypatch.setenv("SOURCE_DB_PORT", "5432")
    monkeypatch.setenv("SOURCE_DB_NAME", "erp_migration_test")
    assert build_jdbc_url() == "jdbc:postgresql://db.internal:5432/erp_migration_test"


@pytest.mark.parametrize("missing", ["SOURCE_DB_HOST", "SOURCE_DB_PORT", "SOURCE_DB_NAME"])
def test_build_jdbc_url_missing_env_raises(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.setenv("SOURCE_DB_HOST", "db.internal")
    monkeypatch.setenv("SOURCE_DB_PORT", "5432")
    monkeypatch.setenv("SOURCE_DB_NAME", "erp_migration_test")
    monkeypatch.delenv(missing, raising=False)
    with pytest.raises(ValueError):
        build_jdbc_url()


def test_quote_identifier_valid() -> None:
    assert quote_identifier("DS") == '"DS"'
    assert quote_identifier("M2201") == '"M2201"'
    assert quote_identifier("my_table_1") == '"my_table_1"'


@pytest.mark.parametrize(
    "bad",
    [
        "a;b",
        "drop table",
        'a"b',
        "a--b",
        "1table",
        "",
        "with space",
        "t;DROP TABLE x",
        "-- comment",
    ],
)
def test_quote_identifier_illegal_raises(bad: str) -> None:
    with pytest.raises(ValueError):
        quote_identifier(bad)


def test_qualified_table_ok() -> None:
    assert qualified_table("DS", "customer") == '"DS"."customer"'
    assert qualified_table("M2201", "M2201") == '"M2201"."M2201"'


def test_qualified_table_schema_not_whitelisted_raises() -> None:
    with pytest.raises(ValueError):
        qualified_table("public", "customer")


def test_qualified_table_illegal_table_raises() -> None:
    with pytest.raises(ValueError):
        qualified_table("DS", "a; DROP TABLE x")
