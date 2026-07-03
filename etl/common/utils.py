"""純函式小工具:時間(UTC+8)、命名正規化等。

不依賴 Spark session,方便單元測試。
"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

TW_TZ = ZoneInfo("Asia/Taipei")


def now_tw() -> datetime:
    """回傳台北時區(UTC+8)的 aware datetime。禁用 utcnow() / naive now()。"""
    return datetime.now(TW_TZ)


def now_tw_iso() -> str:
    """回傳 ISO 8601 + offset 的現在時間字串,例:2026-05-07T14:23:00+08:00。"""
    return now_tw().isoformat(timespec="seconds")


def normalize_name(name: str) -> str:
    """命名正規化:去頭尾空白、轉小寫、非英數轉底線、去重複底線。"""
    lowered = name.strip().lower()
    replaced = re.sub(r"[^0-9a-z]+", "_", lowered)
    return replaced.strip("_")


def is_blank(value: object) -> bool:
    """判斷是否為 None 或去空白後的空字串。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False
