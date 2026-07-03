"""DS schema 專屬轉換:型別 / null / 欄位正規化。

純函式,不依賴 Spark session,方便單元測試;共用邏輯匯入 transforms/common(不改 common.py)。
欄名尾碼慣例決定轉型規則:
  - *_QTY / *_ID / *_ACTIVE → 整數(to_int)
  - *_AMT / *_PRICE        → 浮點(to_float)
  - 其餘                    → 字串並 trim / null 正規化(to_str)
本檔頂層禁 import pyspark(job import 需保持無 pyspark 依賴)。
"""

from __future__ import annotations

from typing import Any

try:  # Glue 上以 transforms.* 執行;fallback 供 repo 根以 etl.transforms.* 匯入
    from transforms.common import to_float, to_int, to_str
except ImportError:  # pragma: no cover
    from etl.transforms.common import to_float, to_int, to_str

# 依欄名尾碼判斷目標型別
_INT_SUFFIXES = ("_QTY", "_ID", "_ACTIVE")
_FLOAT_SUFFIXES = ("_AMT", "_PRICE")


def normalize_value(column: str, value: Any) -> Any:
    """依欄名尾碼將單一欄位值正規化為對應型別。"""
    if column.endswith(_INT_SUFFIXES):
        return to_int(value)
    if column.endswith(_FLOAT_SUFFIXES):
        return to_float(value)
    return to_str(value)


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """對整列(欄名 → 值)套用欄位級正規化,鍵集合保持不變。"""
    return {column: normalize_value(column, value) for column, value in row.items()}
