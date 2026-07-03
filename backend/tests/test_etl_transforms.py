"""transforms / comments 純函式測試:斷言與 v1.0.0 `etl/transforms/*`、`etl/common/ddl.py` 行為一致。

期望值以 v1.0.0 mapping(`etl/config/mapping/ds.yaml` / `m2201.yaml`)與轉換規則為準硬編,
不 import 凍結的 `etl/` 目錄。
"""

import os

# app.core.db 於 import 時建立 engine;測試不連 DB,僅需合法 URL 讓 Settings 可載入
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

import pytest  # noqa: E402

from app.etl.comments import build_column_comments, quote_ident, quote_literal  # noqa: E402
from app.etl.transforms import (  # noqa: E402
    ColumnMapping,
    convert_value,
    infer_ds_transform_type,
    map_row,
    normalize_null,
    to_float,
    to_int,
    to_str,
    trim,
)

# ---------------------------------------------------------------------------
# 基本轉換(v1.0.0 etl/transforms/common.py 行為)
# ---------------------------------------------------------------------------


def test_trim() -> None:
    assert trim("  a b  ") == "a b"
    assert trim(123) == 123
    assert trim(None) is None


@pytest.mark.parametrize("token", ["", "null", "NoNe", " NA ", "-", "n/a", "NaN"])
def test_normalize_null_tokens(token: str) -> None:
    assert normalize_null(token) is None


def test_normalize_null_keeps_real_values() -> None:
    assert normalize_null("0") == "0"
    assert normalize_null(0) == 0
    assert normalize_null("abc") == "abc"


def test_to_int() -> None:
    assert to_int("3") == 3
    assert to_int(" 42 ") == 42
    assert to_int(3.7) == 3
    assert to_int("abc") is None
    assert to_int("abc", default=0) == 0
    assert to_int("3.5") is None  # int("3.5") 失敗,與 v1.0.0 一致
    assert to_int(None) is None
    assert to_int("null") is None


def test_to_float() -> None:
    assert to_float("1.5") == 1.5
    assert to_float(" 2 ") == 2.0
    assert to_float("x") is None
    assert to_float("x", default=0.0) == 0.0
    assert to_float(None) is None


def test_to_str() -> None:
    assert to_str(" a ") == "a"
    assert to_str(123) == "123"
    assert to_str("null") is None
    assert to_str("null", default="") == ""
    assert to_str(None) is None


# ---------------------------------------------------------------------------
# DS 尾碼推斷 + 行為一致性(v1.0.0 etl/transforms/ds.py)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        ("GAT_QTY", "int"),
        ("GAQ_QTY", "int"),
        ("GAM_ID", "int"),
        ("GAM_ACTIVE", "int"),
        ("GAT_AMT", "float"),
        ("GAQ_PRICE", "float"),
        ("GAT_NO", "str"),
        ("GAT_MEMO", "str"),
        ("GAM_NAME", "str"),
    ],
)
def test_infer_ds_transform_type(column: str, expected: str) -> None:
    assert infer_ds_transform_type(column) == expected


def test_ds_row_parity_with_v100_normalize_row() -> None:
    """依尾碼推斷型別後 map_row,結果須與 v1.0.0 ds.normalize_row 一致。"""
    src_row = {
        "GAT_NO": " A1 ",
        "GAT_DATE": "20260101",
        "GAT_QTY": " 3 ",
        "GAT_AMT": "1.5",
        "GAT_MEMO": "null",
    }
    mappings = tuple(
        ColumnMapping(
            source_column=col,
            target_column=col,
            transform_type=infer_ds_transform_type(col),
            comment="佔位",
        )
        for col in src_row
    )
    assert map_row(src_row, mappings) == {
        "GAT_NO": "A1",
        "GAT_DATE": "20260101",
        "GAT_QTY": 3,
        "GAT_AMT": 1.5,
        "GAT_MEMO": None,
    }


# ---------------------------------------------------------------------------
# convert_value 分派(v1.0.0 etl/transforms/m2201.py _convert 行為)
# ---------------------------------------------------------------------------


def test_convert_value_dispatch() -> None:
    assert convert_value(" 3 ", "int") == 3
    assert convert_value("1.5", "float") == 1.5
    assert convert_value(" a ", "str") == "a"


def test_convert_value_null_type_is_passthrough() -> None:
    """transform_type 為 NULL → 不轉換(etl_mappings.transform_type 契約)。"""
    assert convert_value("  raw  ", None) == "  raw  "
    assert convert_value(None, None) is None


def test_convert_value_unknown_type_falls_back_to_str() -> None:
    """未知型別視為 str(v1.0.0 行為)。"""
    assert convert_value(" 3 ", "date") == "3"


# ---------------------------------------------------------------------------
# M2201 mapping 行為一致性(v1.0.0 etl/config/mapping/m2201.yaml 對照)
# ---------------------------------------------------------------------------

# 對照 v1.0.0 m2201.yaml:GAT_FILE / GAQ_FILE 合併列 → M2201 目標列
_M2201_MAPPINGS: tuple[ColumnMapping, ...] = (
    ColumnMapping("GAT_NO", "DOC_NO", "str", "單據編號(主鍵,字串)"),
    ColumnMapping("GAT_DATE", "DOC_DATE", "str", "單據日期(YYYYMMDD 字串)"),
    ColumnMapping("GAT_QTY", "DOC_QTY", "int", "單據數量(整數)"),
    ColumnMapping("GAT_AMT", "DOC_AMT", "float", "單據金額(浮點)"),
    ColumnMapping("GAT_MEMO", "DOC_MEMO", "str", "單據備註(字串)"),
    ColumnMapping("GAQ_CUST", "CUST_CODE", "str", "客戶代號(字串)"),
    ColumnMapping("GAQ_ITEM", "ITEM_CODE", "str", "品項代號(字串)"),
    ColumnMapping("GAQ_PRICE", "UNIT_PRICE", "float", "單價(浮點)"),
    ColumnMapping("GAQ_QTY", "QUOTE_QTY", "int", "報價數量(整數)"),
)


def test_m2201_map_row_parity_with_v100() -> None:
    """欄位對映 / 型別轉換須與 v1.0.0 m2201.map_row 一致(含來源缺欄 → None)。"""
    src_row = {
        "GAT_NO": "D001",
        "GAT_DATE": " 20260102 ",
        "GAT_QTY": "7",
        "GAT_AMT": "99.9",
        "GAT_MEMO": "n/a",
        "GAQ_CUST": "C01",
        "GAQ_ITEM": "I01",
        "GAQ_PRICE": "12.34",
        # GAQ_QTY 缺欄 → QUOTE_QTY None
    }
    assert map_row(src_row, _M2201_MAPPINGS) == {
        "DOC_NO": "D001",
        "DOC_DATE": "20260102",
        "DOC_QTY": 7,
        "DOC_AMT": 99.9,
        "DOC_MEMO": None,
        "CUST_CODE": "C01",
        "ITEM_CODE": "I01",
        "UNIT_PRICE": 12.34,
        "QUOTE_QTY": None,
    }


def test_m2201_target_columns_keep_mapping_order() -> None:
    result = map_row({}, _M2201_MAPPINGS)
    assert list(result.keys()) == [m.target_column for m in _M2201_MAPPINGS]


# ---------------------------------------------------------------------------
# COMMENT ON COLUMN 組裝(v1.0.0 etl/common/ddl.py 行為)
# ---------------------------------------------------------------------------


def test_build_column_comments_one_per_column() -> None:
    stmts = build_column_comments(
        "M2201",
        ["DOC_NO", "DOC_QTY"],
        {"DOC_NO": "單據編號(主鍵,字串)", "DOC_QTY": "單據數量(整數)"},
        schema="M2201",
    )
    assert stmts == [
        "COMMENT ON COLUMN \"M2201\".\"M2201\".\"DOC_NO\" IS '單據編號(主鍵,字串)';",
        "COMMENT ON COLUMN \"M2201\".\"M2201\".\"DOC_QTY\" IS '單據數量(整數)';",
    ]


def test_build_column_comments_escapes_single_quote() -> None:
    stmts = build_column_comments("T", ["A"], {"A": "it's"}, schema="S")
    assert stmts == ["COMMENT ON COLUMN \"S\".\"T\".\"A\" IS 'it''s';"]


def test_build_column_comments_missing_comment_raises() -> None:
    """缺 comment 欄位須 fail(不靜默),訊息列出缺描述欄名。"""
    with pytest.raises(ValueError, match="DOC_QTY"):
        build_column_comments("T", ["DOC_NO", "DOC_QTY"], {"DOC_NO": "有"}, schema="S")


def test_build_column_comments_empty_comment_raises() -> None:
    with pytest.raises(ValueError, match="DOC_NO"):
        build_column_comments("T", ["DOC_NO"], {"DOC_NO": "   "}, schema="S")


def test_quote_ident_whitelist() -> None:
    assert quote_ident("GAT_FILE") == '"GAT_FILE"'
    assert quote_ident("_x$1") == '"_x$1"'
    for bad in ["", "a b", 'a"b', "a;b", "1abc", "a\nb"]:
        with pytest.raises(ValueError):
            quote_ident(bad)


def test_quote_literal_escaping() -> None:
    assert quote_literal("abc") == "'abc'"
    assert quote_literal("a'b") == "'a''b'"
