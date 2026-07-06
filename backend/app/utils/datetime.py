"""時間工具:全棧鎖 Asia/Taipei(00-overview/05-timezone.md)。

各層取現在時間一律 import 本檔的 `now_tw()` / `to_tw()`,禁各 service 自寫。
"""

from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# pyproject 已鎖 tzdata==2026.2;fallback 固定 +8 保留為防禦
# (台灣無 DST,行為等價;fixed.md §6)
try:
    TZ_TAIPEI: tzinfo = ZoneInfo("Asia/Taipei")
except ZoneInfoNotFoundError:  # pragma: no cover
    TZ_TAIPEI = timezone(timedelta(hours=8), "Asia/Taipei")


def now_tw() -> datetime:
    """取現在時間(aware,Asia/Taipei)。"""
    return datetime.now(TZ_TAIPEI)


def to_tw(dt: datetime) -> datetime:
    """任意 datetime 轉 Asia/Taipei;naive 視為 +08 語意直接補 tzinfo(禁雙偏移)。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ_TAIPEI)
    return dt.astimezone(TZ_TAIPEI)


def db_now() -> datetime:
    """DB 時間欄位為 naive TIMESTAMP(+08 語意),寫入前去 tzinfo。"""
    return now_tw().replace(tzinfo=None)
