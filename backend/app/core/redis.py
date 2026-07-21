"""async Redis client + namespaced cache helper(metadata 快照熱點讀取用)。

- URL 由 env `REDIS_URL` 注入(對齊 `worker/broker.py`);缺值 fail-fast(訊息只含變數名)。
- pytest 環境退記憶體 fake(對齊 broker.py 的 InMemoryBroker 慣例),使快取行為可測、免起 redis。
- 僅存非機密快取資料;連線字串不 log。
"""

from __future__ import annotations

import fnmatch
import os
from collections.abc import AsyncIterator
from typing import cast

from redis.asyncio import Redis

# namespaced key 前綴(與其他專案 / DB 隔離)
KEY_PREFIX = "data-center-etl"


def cache_key(*parts: object) -> str:
    """組 namespaced cache key(冒號分隔,前綴固定)。"""
    return ":".join([KEY_PREFIX, *(str(p) for p in parts)])


class _InMemoryRedis:
    """pytest 用記憶體 fake:實作本模組所需 get/set/delete/scan_iter 子集。"""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, name: str) -> str | None:
        return self._store.get(name)

    async def set(
        self, name: str, value: str, ex: int | None = None, nx: bool = False
    ) -> bool | None:
        # 對齊 redis-py 語意:nx=True 且 key 已存在 → 不寫入,回 None
        if nx and name in self._store:
            return None
        self._store[name] = value
        return True

    async def delete(self, *names: str) -> int:
        removed = 0
        for name in names:
            if name in self._store:
                del self._store[name]
                removed += 1
        return removed

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        for key in list(self._store):
            if fnmatch.fnmatch(key, match):
                yield key


_client: Redis | None = None


def get_redis() -> Redis:
    """取得 async redis client(程序內單例);pytest 退記憶體 fake,否則 env 缺值 fail-fast。"""
    global _client
    if _client is None:
        if "PYTEST_VERSION" in os.environ:
            # 型別對外統一為 Redis;fake 於執行期 duck-type,不引入 Any
            _client = cast(Redis, _InMemoryRedis())
        else:
            url = os.environ.get("REDIS_URL")
            if not url:
                raise RuntimeError("缺少必要環境變數:REDIS_URL")
            _client = Redis.from_url(url, decode_responses=True)
    return _client


async def cache_get(key: str) -> str | None:
    """讀快取;未命中回 None。"""
    value = await get_redis().get(key)
    return None if value is None else str(value)


async def cache_set(key: str, value: str, *, ttl_seconds: int) -> None:
    """寫快取(帶 TTL,避免髒讀無限存活)。"""
    await get_redis().set(key, value, ex=ttl_seconds)


async def cache_set_nx(key: str, value: str, *, ttl_seconds: int) -> bool:
    """SET NX(帶 TTL):key 不存在才寫入,回是否寫入成功(跨 process 互斥鎖用)。"""
    result = await get_redis().set(key, value, ex=ttl_seconds, nx=True)
    return bool(result)


async def cache_delete(key: str) -> None:
    """刪除單一 key(釋放互斥鎖 / 清進度 key 用)。"""
    await get_redis().delete(key)


async def delete_pattern(pattern: str) -> None:
    """刪除符合 glob pattern 的所有 key(refresh 後對應 dataset 快取失效用)。"""
    client = get_redis()
    keys = [str(key) async for key in client.scan_iter(match=pattern)]
    if keys:
        await client.delete(*keys)
