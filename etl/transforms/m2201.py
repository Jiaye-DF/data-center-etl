"""GAT_FILE / GAQ_FILE → M2201 欄位對應與型別轉換(設定驅動)。

對照關係一律讀 config["mapping"]["m2201"] 執行,禁把來源→目標對照硬編於本檔。
純函式,不依賴 Spark session,方便單元測試;共用轉換匯入 transforms/common。
"""

from __future__ import annotations

from typing import Any

try:  # Glue 上以 transforms.* 執行;fallback 供 repo 根以 etl.transforms.* 匯入
    from transforms.common import to_float, to_int, to_str
except ImportError:  # pragma: no cover
    from etl.transforms.common import to_float, to_int, to_str

# type 名稱 → 轉換函式;僅型別分派,非來源→目標對照
_CONVERTERS = {
    "str": to_str,
    "int": to_int,
    "float": to_float,
}


def _convert(value: Any, type_name: str) -> Any:
    """依 mapping 的 type 欄位挑轉換函式;未知型別視為 str。"""
    converter = _CONVERTERS.get(type_name, to_str)
    return converter(value)


def target_columns(mapping: dict) -> list[str]:
    """回傳 mapping 定義的目標欄位順序清單。"""
    return [col["target"] for col in mapping.get("columns", [])]


def build_comments(mapping: dict) -> dict[str, str]:
    """由 mapping 組出 {目標欄名: comment}(供 writer 產生 COMMENT ON COLUMN)。"""
    return {col["target"]: col["comment"] for col in mapping.get("columns", [])}


def map_row(src_row: dict, mapping: dict) -> dict:
    """依 mapping 把單筆來源列(GAT_FILE / GAQ_FILE 合併後的 dict)對映為 M2201 目標列。

    - 來源欄名取自 mapping 每欄的 source;缺值以 None 代入後由轉換函式處理。
    - 型別轉換依 mapping 每欄的 type 分派 transforms.common 對應函式。
    - 對照關係全數來自 mapping,不硬編。
    """
    result: dict[str, Any] = {}
    for col in mapping.get("columns", []):
        raw = src_row.get(col["source"])
        result[col["target"]] = _convert(raw, col.get("type", "str"))
    return result
