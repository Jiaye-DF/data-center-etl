"""權限設定 Redis 讀取快取層測試(v1.6.1 task-003)。

純單元測試(不連 DB / 不連 Redis):以本檔記憶體 fake 取代 `permission_cache.get_redis`
(對齊 `test_api_client_rate_limit.py` 慣例,每測試一份新替身,狀態天然隔離),
並可注入指令級故障驗證降級直讀。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Final
from uuid import uuid4

import pytest
from pydantic import BaseModel, JsonValue

from app.services import permission_cache
from app.services.permission_cache import (
    DEFAULT_TTL_SECONDS,
    EFFECTIVE_PREFIX,
    KEY_PREFIX,
    LIST_PREFIX,
    effective_key,
    get_or_load,
    get_or_load_model,
    invalidate,
    invalidate_all_effective,
    invalidate_clients,
    invalidate_lists,
    invalidate_prefix,
    list_key,
)

KEY: Final = f"{KEY_PREFIX}test:sample"


class FakeRedis:
    """記憶體 Redis 替身:實作本層用到的 get / set(ex) / delete / scan_iter 子集。

    `fail_on` 內的指令名會拋 `ConnectionError`,用來模擬 Redis 故障(連線中斷 / timeout)。
    """

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttl: dict[str, int] = {}
        self.fail_on: set[str] = set()
        self.delete_batches: list[int] = []

    def _guard(self, command: str) -> None:
        if command in self.fail_on:
            raise ConnectionError(f"redis {command} 連線中斷")

    async def get(self, name: str) -> str | None:
        self._guard("get")
        return self.store.get(name)

    async def set(self, name: str, value: str, ex: int | None = None) -> bool:
        self._guard("set")
        self.store[name] = value
        if ex is not None:
            self.ttl[name] = ex
        return True

    async def delete(self, *names: str) -> int:
        self._guard("delete")
        self.delete_batches.append(len(names))
        removed = 0
        for name in names:
            if self.store.pop(name, None) is not None:
                self.ttl.pop(name, None)
                removed += 1
        return removed

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        self._guard("scan_iter")
        prefix = match.removesuffix("*")
        for name in list(self.store):
            if name.startswith(prefix):
                yield name


@pytest.fixture
def redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    fake = FakeRedis()
    monkeypatch.setattr(permission_cache, "get_redis", lambda: fake)
    return fake


class CountingLoader:
    """回源替身:記錄呼叫次數,回值可隨時抽換(驗證失效後拿到新值)。"""

    def __init__(self, value: JsonValue) -> None:
        self.value = value
        self.calls = 0

    async def __call__(self) -> JsonValue:
        self.calls += 1
        return self.value


def _loader(value: JsonValue) -> CountingLoader:
    return CountingLoader(value)


# ── key 命名(下游 task 依賴的對外契約)─────────────────────────────────
def test_key_builders_follow_prefix_contract() -> None:
    client_uid = uuid4()
    assert effective_key(client_uid) == f"client_setting:effective:{client_uid}"
    assert list_key("services") == "client_setting:list:services"
    assert list_key("operations", "service", 7) == "client_setting:list:operations:service:7"
    assert EFFECTIVE_PREFIX.startswith(KEY_PREFIX)
    assert LIST_PREFIX.startswith(KEY_PREFIX)


# ── cache-aside 基本行為 ────────────────────────────────────────────────
async def test_miss_calls_loader_and_fills_cache_with_ttl(redis: FakeRedis) -> None:
    loader = _loader({"O1": {"T1": {"C11": "read"}}})

    result = await get_or_load(KEY, loader)

    assert result == {"O1": {"T1": {"C11": "read"}}}
    assert loader.calls == 1
    assert json.loads(redis.store[KEY]) == loader.value
    assert redis.ttl[KEY] == DEFAULT_TTL_SECONDS


async def test_second_read_hits_cache_and_skips_loader(redis: FakeRedis) -> None:
    loader = _loader(["a", "b"])

    first = await get_or_load(KEY, loader)
    loader.value = ["changed-behind-cache"]
    second = await get_or_load(KEY, loader)

    assert first == ["a", "b"]
    assert second == ["a", "b"]
    assert loader.calls == 1


async def test_custom_ttl_is_applied(redis: FakeRedis) -> None:
    await get_or_load(KEY, _loader(1), ttl_seconds=30)

    assert redis.ttl[KEY] == 30


async def test_ttl_must_be_positive(redis: FakeRedis) -> None:
    loader = _loader(1)
    with pytest.raises(ValueError):
        await get_or_load(KEY, loader, ttl_seconds=0)
    assert loader.calls == 0


async def test_empty_values_are_cached_not_treated_as_miss(redis: FakeRedis) -> None:
    """`None` / 空集合是合法權限結構(無 Role 無臨時權限),不得被當成未命中反覆回源。"""
    for value in (None, [], {}):
        redis.store.clear()
        loader = _loader(value)
        assert await get_or_load(KEY, loader) == value
        assert await get_or_load(KEY, loader) == value
        assert loader.calls == 1


async def test_corrupt_cache_value_falls_back_to_loader(
    redis: FakeRedis, caplog: pytest.LogCaptureFixture
) -> None:
    redis.store[KEY] = "{壞掉的內容"
    loader = _loader({"ok": True})

    with caplog.at_level(logging.WARNING):
        result = await get_or_load(KEY, loader)

    assert result == {"ok": True}
    assert loader.calls == 1
    assert json.loads(redis.store[KEY]) == {"ok": True}


async def test_unserializable_value_skips_cache_but_still_returns(
    redis: FakeRedis, caplog: pytest.LogCaptureFixture
) -> None:
    """loader 給了非 JSON 結構(契約違規)只放棄快取,讀取路徑不因此失敗。"""

    async def loader() -> JsonValue:
        return {"expires_at": object()}  # type: ignore[dict-item]

    with caplog.at_level(logging.WARNING):
        result = await get_or_load(KEY, loader)

    assert isinstance(result, dict)
    assert redis.store == {}


# ── 異動即失效 ──────────────────────────────────────────────────────────
async def test_invalidate_forces_reload_with_new_value(redis: FakeRedis) -> None:
    loader = _loader({"version": 1})
    await get_or_load(KEY, loader)

    await invalidate(KEY)
    loader.value = {"version": 2}
    result = await get_or_load(KEY, loader)

    assert result == {"version": 2}
    assert loader.calls == 2


async def test_invalidate_without_keys_is_noop(redis: FakeRedis) -> None:
    await invalidate()

    assert redis.delete_batches == []


async def test_invalidate_clients_only_drops_those_clients(redis: FakeRedis) -> None:
    kept, dropped = uuid4(), uuid4()
    await get_or_load(effective_key(kept), _loader("kept"))
    await get_or_load(effective_key(dropped), _loader("dropped"))

    await invalidate_clients(dropped)

    assert effective_key(kept) in redis.store
    assert effective_key(dropped) not in redis.store


async def test_invalidate_prefix_drops_only_matching_namespace(redis: FakeRedis) -> None:
    await get_or_load(effective_key(uuid4()), _loader(1))
    await get_or_load(effective_key(uuid4()), _loader(2))
    await get_or_load(list_key("services"), _loader(3))
    redis.store["rate_limit:client:other"] = "keep"

    await invalidate_all_effective()

    assert list(redis.store) == [list_key("services"), "rate_limit:client:other"]

    await invalidate_lists()

    assert list(redis.store) == ["rate_limit:client:other"]


async def test_invalidate_prefix_rejects_foreign_prefix(redis: FakeRedis) -> None:
    """防呆:前綴須落在本層命名空間,避免誤刪限流 / 快照等他模組 key。"""
    redis.store["rate_limit:client:x"] = "keep"

    for prefix in ("", "rate_limit:", "data-center-etl:"):
        with pytest.raises(ValueError):
            await invalidate_prefix(prefix)

    assert redis.store["rate_limit:client:x"] == "keep"


async def test_invalidate_prefix_deletes_in_batches(redis: FakeRedis) -> None:
    """key 量大時分批 DEL(不把上千 key 塞進單一指令)。"""
    for index in range(1200):
        redis.store[f"{EFFECTIVE_PREFIX}{index}"] = "x"

    await invalidate_all_effective()

    assert redis.store == {}
    assert redis.delete_batches == [500, 500, 200]


# ── Redis 故障降級直讀 ──────────────────────────────────────────────────
async def test_get_failure_degrades_to_loader(
    redis: FakeRedis, caplog: pytest.LogCaptureFixture
) -> None:
    redis.fail_on = {"get"}
    loader = _loader({"from": "rds"})

    with caplog.at_level(logging.WARNING):
        first = await get_or_load(KEY, loader)
        second = await get_or_load(KEY, loader)

    assert first == second == {"from": "rds"}
    assert loader.calls == 2  # 每次都回源,功能不中斷
    assert any("權限快取降級" in record.getMessage() for record in caplog.records)


async def test_set_failure_still_returns_loader_value(redis: FakeRedis) -> None:
    redis.fail_on = {"set"}
    loader = _loader([1, 2, 3])

    assert await get_or_load(KEY, loader) == [1, 2, 3]
    assert redis.store == {}


async def test_total_redis_outage_does_not_raise(redis: FakeRedis) -> None:
    """Redis 全掛(含 client 取得失敗):讀取照常、失效不擋主流程。"""
    redis.fail_on = {"get", "set", "delete", "scan_iter"}
    loader = _loader({"ok": 1})

    assert await get_or_load(KEY, loader) == {"ok": 1}
    await invalidate(KEY)
    await invalidate_clients(uuid4())
    await invalidate_all_effective()
    await invalidate_lists()


async def test_client_construction_failure_degrades(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> FakeRedis:
        raise RuntimeError("REDIS_URL 不可用")

    monkeypatch.setattr(permission_cache, "get_redis", _boom)
    loader = _loader("直讀 RDS")

    assert await get_or_load(KEY, loader) == "直讀 RDS"
    await invalidate(KEY)
    await invalidate_all_effective()


# ── Pydantic 模型版 ─────────────────────────────────────────────────────
class _Preview(BaseModel):
    client_uid: str
    permissions: dict[str, dict[str, str]]


async def test_model_variant_round_trips_and_hits(redis: FakeRedis) -> None:
    model = _Preview(client_uid="c-1", permissions={"T1": {"C11": "read"}})
    calls = 0

    async def loader() -> _Preview:
        nonlocal calls
        calls += 1
        return model

    first = await get_or_load_model(KEY, _Preview, loader)
    second = await get_or_load_model(KEY, _Preview, loader)

    assert first == second == model
    assert calls == 1
    assert redis.ttl[KEY] == DEFAULT_TTL_SECONDS


async def test_model_variant_reloads_on_schema_mismatch(redis: FakeRedis) -> None:
    """快取內容與現行 schema 不符(舊版格式)→ 視為未命中並以新格式覆寫。"""
    redis.store[KEY] = json.dumps({"legacy": True})
    model = _Preview(client_uid="c-1", permissions={})

    async def loader() -> _Preview:
        return model

    assert await get_or_load_model(KEY, _Preview, loader) == model
    assert json.loads(redis.store[KEY]) == {"client_uid": "c-1", "permissions": {}}


async def test_model_variant_degrades_on_redis_failure(redis: FakeRedis) -> None:
    redis.fail_on = {"get", "set"}
    model = _Preview(client_uid="c-1", permissions={})

    async def loader() -> _Preview:
        return model

    assert await get_or_load_model(KEY, _Preview, loader) == model


# ── 併發 ────────────────────────────────────────────────────────────────
async def test_concurrent_misses_all_get_correct_value(redis: FakeRedis) -> None:
    """同 key 併發未命中:各自回源不互相汙染,最終快取內容一致(回源冪等)。"""
    loader = _loader({"O1": {"T1": {"C11": "read"}}})
    started = asyncio.Event()

    async def slow_loader() -> JsonValue:
        started.set()
        await asyncio.sleep(0)
        return await loader()

    results = await asyncio.gather(*(get_or_load(KEY, slow_loader) for _ in range(10)))

    assert all(result == loader.value for result in results)
    assert json.loads(redis.store[KEY]) == loader.value
    assert started.is_set()


async def test_invalidate_during_concurrent_reads_keeps_next_read_fresh(
    redis: FakeRedis,
) -> None:
    """失效與併發讀取交錯後,再次讀取仍拿得到新值(舊值最遲由 TTL 收斂)。"""
    loader = _loader({"version": 1})

    async def reader() -> JsonValue:
        return await get_or_load(KEY, loader)

    await asyncio.gather(reader(), reader(), invalidate(KEY), reader())

    await invalidate(KEY)
    loader.value = {"version": 2}

    assert await get_or_load(KEY, loader) == {"version": 2}


async def test_plain_callable_loader_supported(redis: FakeRedis) -> None:
    """loader 不限本檔替身:一般 async 函式同樣適用。"""

    async def loader() -> JsonValue:
        return "plain"

    assert await get_or_load(KEY, loader) == "plain"
