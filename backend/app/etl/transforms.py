"""欄位轉換(移植 v1.0.0 `etl/transforms/*` 行為;v1.1.0 改由 DB mapping 設定驅動)。

- trim / null 正規化 / to_int / to_float / to_str 與 v1.0.0 `etl/transforms/common.py` 一致。
- convert_value 依 mapping 的 transform_type 分派(對齊 v1.0.0 `etl/transforms/m2201.py`:
  未知型別視為 str;transform_type 為 NULL 則不轉換)。
- infer_ds_transform_type 依欄名尾碼推斷型別(對齊 v1.0.0 `etl/transforms/ds.py` 尾碼慣例),
  供 seed(task-008)與行為一致性測試使用。

純函式,不依賴 DB session,方便單元測試。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# 視為 null 的字串(去空白、轉小寫後比對;與 v1.0.0 一致)
_NULL_TOKENS = {"", "null", "none", "nan", "na", "n/a", "-"}

# v1.0.0 etl/transforms/ds.py 欄名尾碼慣例
_DS_INT_SUFFIXES = ("_QTY", "_ID", "_ACTIVE")
_DS_FLOAT_SUFFIXES = ("_AMT", "_PRICE")


@dataclass(frozen=True)
class ColumnMapping:
    """單一欄位對照:來源欄 → 目標欄 + 型別轉換 + Comment(對應 etl_mappings 一列)。"""

    source_column: str
    target_column: str
    transform_type: str | None
    comment: str


def trim(value: Any) -> Any:
    """字串去頭尾空白;非字串原樣回傳。"""
    if isinstance(value, str):
        return value.strip()
    return value


def normalize_null(value: Any) -> Any:
    """將常見 null 佔位字串正規化為 None。"""
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in _NULL_TOKENS:
        return None
    return value


def to_int(value: Any, default: int | None = None) -> int | None:
    """轉整數;無法轉換回傳 default。"""
    value = normalize_null(trim(value))
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float | None = None) -> float | None:
    """轉浮點;無法轉換回傳 default。"""
    value = normalize_null(trim(value))
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_str(value: Any, default: str | None = None) -> str | None:
    """轉字串並 trim;null 佔位回傳 default。"""
    value = normalize_null(trim(value))
    if value is None:
        return default
    return str(value)


# transform_type 名稱 → 轉換函式;僅型別分派,對照關係一律由 mapping 驅動
_CONVERTERS: dict[str, Callable[[Any], Any]] = {
    "str": to_str,
    "int": to_int,
    "float": to_float,
}


def infer_ds_transform_type(column: str) -> str:
    """依欄名尾碼推斷 DS 欄位的 transform_type(v1.0.0 ds.normalize_value 行為)。"""
    if column.endswith(_DS_INT_SUFFIXES):
        return "int"
    if column.endswith(_DS_FLOAT_SUFFIXES):
        return "float"
    return "str"


def convert_value(value: Any, transform_type: str | None) -> Any:
    """依 transform_type 轉換單一值。

    - NULL(None)→ 不轉換,原值回傳(etl_mappings.transform_type 契約)。
    - 未知型別 → 視為 str(v1.0.0 m2201._convert 行為)。
    """
    if transform_type is None:
        return value
    converter: Callable[[Any], Any] = _CONVERTERS.get(transform_type, to_str)
    return converter(value)


def map_row(src_row: Mapping[str, Any], mappings: Sequence[ColumnMapping]) -> dict[str, Any]:
    """依 mapping 把單筆來源列對映為目標列。

    - 來源缺欄以 None 代入後交由轉換函式處理(v1.0.0 m2201.map_row 行為)。
    - 對照關係全數來自 mappings,不硬編。
    """
    return {
        m.target_column: convert_value(src_row.get(m.source_column), m.transform_type)
        for m in mappings
    }
