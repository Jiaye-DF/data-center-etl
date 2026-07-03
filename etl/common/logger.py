"""標準 logging 包裝(structured)。

log 時戳一律 ISO 8601 + 08:00;可帶 job 名 / 表名 / 筆數等結構欄位。
機密(token / password / connection string)禁進 log,呼叫端自行過濾。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

try:  # 相對 import 供 Glue 上以 common.* 執行;fallback 供 repo 根以 etl.common.* 匯入
    from common.utils import TW_TZ
except ImportError:  # pragma: no cover
    from etl.common.utils import TW_TZ


class TaipeiJsonFormatter(logging.Formatter):
    """輸出 JSON 結構化 log,時戳為台北時區 ISO 8601 + offset。"""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, TW_TZ).isoformat(timespec="seconds")
        payload: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # 附掛結構欄位(job 名 / 表名 / 筆數等)
        extra = getattr(record, "context", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "etl", level: int = logging.INFO) -> logging.Logger:
    """取得已掛好台北時區 JSON formatter 的 logger。"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(TaipeiJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger


def log_event(
    logger: logging.Logger,
    msg: str,
    *,
    job: str | None = None,
    table: str | None = None,
    rows: int | None = None,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """帶結構欄位的 log 便捷函式。"""
    context: dict[str, Any] = {}
    if job is not None:
        context["job"] = job
    if table is not None:
        context["table"] = table
    if rows is not None:
        context["rows"] = rows
    context.update(fields)
    logger.log(level, msg, extra={"context": context})
