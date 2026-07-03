"""共用轉換 helper 基底:trim / 型別轉換 / null 正規化。

純函式,不依賴 Spark session,方便單元測試;供 004/005 job 匯入,兩者不改本檔。
"""

from __future__ import annotations

from typing import Any

# 視為 null 的字串(去空白、轉小寫後比對)
_NULL_TOKENS = {"", "null", "none", "nan", "na", "n/a", "-"}


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
