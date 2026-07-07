"""taskiq broker:redis 佇列(URL 由 env `REDIS_URL` 注入,缺值 fail-fast)。

worker 啟動指令(消費佇列、執行 mirror_sync;供 task-012 容器 command 使用):

    uv run taskiq worker app.worker.tasks:broker
"""

from __future__ import annotations

import os

from taskiq import AsyncBroker, InMemoryBroker
from taskiq_redis import ListQueueBroker


def create_broker() -> AsyncBroker:
    """建立 broker:pytest 環境退 InMemoryBroker,否則以 env `REDIS_URL` 連 redis。

    - pytest(8.2+ 啟動即設 `PYTEST_VERSION`)→ InMemoryBroker,
      `await_inplace=True` 使 kiq 就地執行完畢,測試斷言免輪詢。
    - 其餘環境缺 `REDIS_URL` 即 fail-fast(訊息只含變數名,不含值;02-secrets.md)。
    """
    if "PYTEST_VERSION" in os.environ:
        return InMemoryBroker(await_inplace=True)
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        raise RuntimeError("缺少必要環境變數:REDIS_URL")
    # socket_timeout=None:redis-py 8 預設 read timeout 5s 會使閒置 BRPOP 反覆
    # TimeoutError → taskiq 子行程無限 reload(fixed.md §19),明確關閉
    return ListQueueBroker(url=redis_url, socket_timeout=None)


broker: AsyncBroker = create_broker()
