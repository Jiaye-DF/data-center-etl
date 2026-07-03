"""transforms/m2201 對映純函式測試(不需連 DB / Spark)。

涵蓋:GAT/GAQ 欄位 → M2201 欄位對映正確、每個目標欄位皆帶非空 comment。
mapping 直接讀 config/mapping/m2201.yaml,確保與實際設定對齊。
"""

from __future__ import annotations

from pathlib import Path

import yaml

try:  # Glue 上以 transforms.* 執行;fallback 供 repo 根以 etl.transforms.* 匯入
    from transforms.m2201 import build_comments, map_row, target_columns
except ImportError:  # pragma: no cover
    from etl.transforms.m2201 import build_comments, map_row, target_columns

_MAPPING_PATH = Path(__file__).resolve().parent.parent / "config" / "mapping" / "m2201.yaml"


def _load_mapping() -> dict:
    with _MAPPING_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_map_row_maps_source_to_target_columns():
    """給合併後的來源列,map_row 輸出目標欄名與轉換後的值皆正確。"""
    mapping = _load_mapping()
    src_row = {
        "GAT_NO": "  D001 ",
        "GAT_DATE": "20260703",
        "GAT_QTY": "12",
        "GAT_AMT": "99.5",
        "GAT_MEMO": "測試",
        "GAQ_CUST": "C100",
        "GAQ_ITEM": "IT200",
        "GAQ_PRICE": "3.25",
        "GAQ_QTY": "7",
    }
    out = map_row(src_row, mapping)

    # 目標欄集合 == mapping 目標欄集合
    assert set(out.keys()) == set(target_columns(mapping))

    # 值對映 + 型別轉換正確
    assert out["DOC_NO"] == "D001"          # str + trim
    assert out["DOC_DATE"] == "20260703"
    assert out["DOC_QTY"] == 12             # int
    assert out["DOC_AMT"] == 99.5           # float
    assert out["DOC_MEMO"] == "測試"
    assert out["CUST_CODE"] == "C100"       # 來自 GAQ_FILE
    assert out["ITEM_CODE"] == "IT200"
    assert out["UNIT_PRICE"] == 3.25
    assert out["QUOTE_QTY"] == 7


def test_map_row_handles_missing_and_null_source():
    """來源缺欄 / null 佔位 → 轉換後為 None,目標欄仍齊全。"""
    mapping = _load_mapping()
    out = map_row({"GAT_NO": "-", "GAT_QTY": "abc"}, mapping)
    assert set(out.keys()) == set(target_columns(mapping))
    assert out["DOC_NO"] is None    # "-" 視為 null
    assert out["DOC_QTY"] is None   # 無法轉整數
    assert out["CUST_CODE"] is None  # 來源缺欄


def test_every_target_column_has_comment():
    """每個目標欄位皆帶非空 comment,且 comments key 集合 == 目標欄集合。"""
    mapping = _load_mapping()
    comments = build_comments(mapping)
    targets = target_columns(mapping)

    assert set(comments.keys()) == set(targets)
    for col in mapping["columns"]:
        assert col.get("comment"), f"目標欄 {col['target']} 缺 comment"
        assert str(comments[col["target"]]).strip() != ""


def test_mapping_covers_both_gat_and_gaq_sources():
    """對照涵蓋 GAT_FILE 與 GAQ_FILE 兩來源。"""
    mapping = _load_mapping()
    sources = {col["source_table"] for col in mapping["columns"]}
    assert "GAT_FILE" in sources
    assert "GAQ_FILE" in sources
