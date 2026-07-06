"""統一 logging 組態(03-backend/05-exceptions-and-logging.md;scan R-LOG-005)。

- 時戳 ISO 8601 + `+08:00` offset(container / 本機皆鎖 Asia/Taipei,05-timezone.md)。
- 結構化欄位:app_name 固定入 format;request_id 由 main.py middleware 產生,
  掛 `request.state.request_id` 並回 `X-Request-ID` header,請求完成行一併輸出。
- level 由 env `LOG_LEVEL` 注入(預設 INFO);worker / scheduler 與 API 同一組態
  (未組態時 root logger 預設 WARNING,engine 的逐表 info 會被靜音)。
"""

from __future__ import annotations

import logging
import os

_APP_NAME = "data-center-etl"
_FORMAT = f"%(asctime)s.%(msecs)03d+08:00 [%(levelname)s] {_APP_NAME} %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S"

_configured = False


def setup_logging() -> None:
    """冪等初始化 root logger;API(main.py)與 worker / scheduler 入口皆呼叫。"""
    global _configured
    if _configured:
        return
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format=_FORMAT, datefmt=_DATEFMT)
    _configured = True
