"""transforms/ds 純轉換函式的單元測試(不需 Spark / DB)。

另含 ds.yaml 契約斷言:每個 mapping 欄位皆有非空 comment,
且 yaml 欄名可被 normalize_value 正確依尾碼轉型。
"""

from __future__ import annotations

from pathlib import Path

import yaml

try:  # Glue 上以 transforms.* 執行;fallback 供 repo 根以 etl.transforms.* 匯入
    from transforms.ds import normalize_row, normalize_value
except ImportError:  # pragma: no cover
    from etl.transforms.ds import normalize_row, normalize_value

_DS_YAML = Path(__file__).resolve().parent.parent / "config" / "mapping" / "ds.yaml"


def test_int_suffix_columns_to_int():
    assert normalize_value("GAT_QTY", " 12 ") == 12
    assert normalize_value("GAM_ID", "7") == 7
    assert normalize_value("GAM_ACTIVE", "1") == 1


def test_float_suffix_columns_to_float():
    assert normalize_value("GAT_AMT", " 3.5 ") == 3.5
    assert normalize_value("GAQ_PRICE", "10") == 10.0


def test_default_columns_to_str_and_trim():
    assert normalize_value("GAT_MEMO", "  hi  ") == "hi"
    assert normalize_value("GAM_NAME", "abc") == "abc"


def test_null_tokens_normalized():
    assert normalize_value("GAT_MEMO", "  null ") is None
    assert normalize_value("GAT_QTY", "N/A") is None
    assert normalize_value("GAT_AMT", "-") is None


def test_unparseable_numeric_returns_none():
    assert normalize_value("GAT_QTY", "abc") is None
    assert normalize_value("GAT_AMT", "x") is None


def test_normalize_row_keeps_keys():
    row = {"GAT_NO": " A1 ", "GAT_QTY": "3", "GAT_AMT": "2.5"}
    out = normalize_row(row)
    assert set(out.keys()) == set(row.keys())
    assert out == {"GAT_NO": "A1", "GAT_QTY": 3, "GAT_AMT": 2.5}


def test_ds_yaml_every_column_has_nonempty_comment():
    """契約:tables.*.columns.* 每欄皆有非空 comment。"""
    data = yaml.safe_load(_DS_YAML.read_text(encoding="utf-8"))
    tables = data["tables"]
    assert tables, "ds.yaml tables 不可為空"
    for table_name, table_def in tables.items():
        columns = table_def["columns"]
        assert columns, f"{table_name} columns 不可為空"
        for col, spec in columns.items():
            comment = spec.get("comment")
            assert isinstance(comment, str) and comment.strip(), (
                f"{table_name}.{col} 缺非空 comment"
            )
