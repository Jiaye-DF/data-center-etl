"""task-003 per-Client 限流(ZSET 雙窗口)+ 連續失敗鎖定測試。

Redis 走本檔記憶體 fake(對齊 `app/core/redis.py` 的 pytest fake 慣例;etl_redis 未映射
host port,且 core fake 未實作 ZSET / TTL 指令),以 monkeypatch 換掉 `rate_limit.get_redis`
與 `rate_limit._now_ms`,使窗口滑動 / TTL 到期可決定性驗證。
"""

import logging
import math
from pathlib import Path

import pytest

from app.api_client_router.common import rate_limit
from app.api_client_router.common.rate_limit import (
    AUTH_FAIL_TTL_SECONDS,
    AUTH_LOCK_TTL_SECONDS,
    DEFAULT_LIMIT_PER_10MIN,
    DEFAULT_LIMIT_PER_MINUTE,
    check_auth_lock,
    check_rate_limit,
    clear_auth_failures,
    register_auth_failure,
)

CLIENT_ID = "client-abc"
RATE_KEY = f"rate_limit:client:{CLIENT_ID}"
FAIL_KEY = f"auth_fail:client:{CLIENT_ID}"
LOCK_KEY = f"auth_lock:client:{CLIENT_ID}"


class FakeRedis:
    """記憶體 Redis 替身:實作本模組用到的 ZSET / 字串 / TTL 指令子集,時鐘由測試推進。"""

    def __init__(self) -> None:
        self.clock_ms = 1_700_000_000_000
        self._zsets: dict[str, dict[str, float]] = {}
        self._values: dict[str, str] = {}
        self._expire_at: dict[str, int] = {}

    # ── 測試輔助 ────────────────────────────────────────────────────────
    def advance(self, seconds: float) -> None:
        self.clock_ms += int(seconds * 1000)

    def keys(self) -> set[str]:
        self._purge()
        return set(self._zsets) | set(self._values)

    def _purge(self) -> None:
        for key, expire_at in list(self._expire_at.items()):
            if expire_at <= self.clock_ms:
                self._zsets.pop(key, None)
                self._values.pop(key, None)
                del self._expire_at[key]

    @staticmethod
    def _bound(raw: str | float | int, fallback: float) -> float:
        if isinstance(raw, str) and raw.lstrip("+-").lower() == "inf":
            return fallback
        return float(raw)

    def _in_range(self, key: str, min: str | float, max: str | float) -> list[tuple[str, float]]:
        lo = self._bound(min, float("-inf"))
        hi = self._bound(max, float("inf"))
        pairs = [(m, s) for m, s in self._zsets.get(key, {}).items() if lo <= s <= hi]
        return sorted(pairs, key=lambda pair: (pair[1], pair[0]))

    # ── ZSET ───────────────────────────────────────────────────────────
    async def zadd(self, name: str, mapping: dict[str, float]) -> int:
        self._purge()
        zset = self._zsets.setdefault(name, {})
        for member, score in mapping.items():
            zset[member] = float(score)
        return len(mapping)

    async def zremrangebyscore(self, name: str, min: str | float, max: str | float) -> int:
        self._purge()
        doomed = self._in_range(name, min, max)
        for member, _ in doomed:
            del self._zsets[name][member]
        return len(doomed)

    async def zcount(self, name: str, min: str | float, max: str | float) -> int:
        self._purge()
        return len(self._in_range(name, min, max))

    async def zrangebyscore(
        self,
        name: str,
        min: str | float,
        max: str | float,
        start: int | None = None,
        num: int | None = None,
        withscores: bool = False,
    ) -> list[tuple[str, float]] | list[str]:
        self._purge()
        pairs = self._in_range(name, min, max)
        if start is not None and num is not None:
            pairs = pairs[start : start + num]
        return pairs if withscores else [member for member, _ in pairs]

    # ── 字串 / TTL ──────────────────────────────────────────────────────
    async def get(self, name: str) -> str | None:
        self._purge()
        return self._values.get(name)

    async def set(self, name: str, value: str, ex: int | None = None) -> bool:
        self._purge()
        self._values[name] = value
        if ex is not None:
            self._expire_at[name] = self.clock_ms + ex * 1000
        return True

    async def incr(self, name: str) -> int:
        self._purge()
        value = int(self._values.get(name, "0")) + 1
        self._values[name] = str(value)
        return value

    async def expire(self, name: str, seconds: int) -> bool:
        self._purge()
        if name not in self._zsets and name not in self._values:
            return False
        self._expire_at[name] = self.clock_ms + seconds * 1000
        return True

    async def ttl(self, name: str) -> int:
        self._purge()
        if name not in self._zsets and name not in self._values:
            return -2
        expire_at = self._expire_at.get(name)
        if expire_at is None:
            return -1
        return math.ceil((expire_at - self.clock_ms) / 1000)

    async def delete(self, *names: str) -> int:
        self._purge()
        removed = 0
        for name in names:
            if name in self._zsets or name in self._values:
                self._zsets.pop(name, None)
                self._values.pop(name, None)
                self._expire_at.pop(name, None)
                removed += 1
        return removed


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    fake = FakeRedis()
    monkeypatch.setattr(rate_limit, "get_redis", lambda: fake)
    monkeypatch.setattr(rate_limit, "_now_ms", lambda: fake.clock_ms)
    return fake


@pytest.fixture
def broken_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> FakeRedis:
        raise RuntimeError("redis 連線中斷")

    monkeypatch.setattr(rate_limit, "get_redis", _boom)


# ── 限流:每分鐘窗口 ────────────────────────────────────────────────────
async def test_minute_window_allows_up_to_limit(fake_redis: FakeRedis) -> None:
    for _ in range(DEFAULT_LIMIT_PER_MINUTE):
        result = await check_rate_limit(
            CLIENT_ID, DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN
        )
        assert result.allowed is True
        assert result.retry_after_seconds == 0
        assert result.degraded is False


async def test_minute_window_blocks_31st_request(fake_redis: FakeRedis) -> None:
    for _ in range(DEFAULT_LIMIT_PER_MINUTE):
        await check_rate_limit(CLIENT_ID, DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN)

    result = await check_rate_limit(CLIENT_ID, DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN)
    assert result.allowed is False
    assert result.retry_after_seconds > 0
    assert result.retry_after_seconds <= rate_limit.MINUTE_WINDOW_SECONDS
    assert result.window_seconds == rate_limit.MINUTE_WINDOW_SECONDS
    assert result.limit == DEFAULT_LIMIT_PER_MINUTE
    assert result.degraded is False


async def test_ten_minute_window_blocks_201st_request(fake_redis: FakeRedis) -> None:
    # 每分鐘上限放寬,單獨驗 10 分鐘窗:每次請求推進 2 秒(共 400 秒 < 600 秒)
    for _ in range(DEFAULT_LIMIT_PER_10MIN):
        result = await check_rate_limit(CLIENT_ID, 10_000, DEFAULT_LIMIT_PER_10MIN)
        assert result.allowed is True
        fake_redis.advance(2)

    result = await check_rate_limit(CLIENT_ID, 10_000, DEFAULT_LIMIT_PER_10MIN)
    assert result.allowed is False
    assert result.window_seconds == rate_limit.TEN_MINUTE_WINDOW_SECONDS
    assert result.limit == DEFAULT_LIMIT_PER_10MIN
    assert result.retry_after_seconds > 0


async def test_window_slides_and_recovers(fake_redis: FakeRedis) -> None:
    for _ in range(DEFAULT_LIMIT_PER_MINUTE + 1):
        await check_rate_limit(CLIENT_ID, DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN)
    assert (
        await check_rate_limit(CLIENT_ID, DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN)
    ).allowed is False

    fake_redis.advance(rate_limit.MINUTE_WINDOW_SECONDS + 1)
    recovered = await check_rate_limit(
        CLIENT_ID, DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN
    )
    assert recovered.allowed is True
    assert recovered.window_seconds == 0


async def test_retry_after_seconds_is_honored_exactly(fake_redis: FakeRedis) -> None:
    """回歸 AD-134:打滿限額 → 429 附 Retry-After → 恰好等滿該秒數重試必放行。

    放行才計數:被拒請求不 zadd,Retry-After 不會被重試本身不斷推遲。
    """
    for _ in range(DEFAULT_LIMIT_PER_MINUTE):
        allowed = await check_rate_limit(
            CLIENT_ID, DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN
        )
        assert allowed.allowed is True

    blocked = await check_rate_limit(CLIENT_ID, DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds >= 1

    # 被拒後再拒一次,Retry-After 不得因重試而延長(拒絕不計數)
    blocked_again = await check_rate_limit(
        CLIENT_ID, DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN
    )
    assert blocked_again.allowed is False
    assert blocked_again.retry_after_seconds <= blocked.retry_after_seconds

    fake_redis.advance(blocked.retry_after_seconds)
    retried = await check_rate_limit(CLIENT_ID, DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN)
    assert retried.allowed is True


async def test_rate_limit_key_name_is_exactly_specified_format(fake_redis: FakeRedis) -> None:
    await check_rate_limit(CLIENT_ID, DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN)
    assert fake_redis.keys() == {RATE_KEY}
    assert await fake_redis.ttl(RATE_KEY) == rate_limit.TEN_MINUTE_WINDOW_SECONDS


async def test_rate_limit_is_per_client(fake_redis: FakeRedis) -> None:
    for _ in range(DEFAULT_LIMIT_PER_MINUTE + 1):
        await check_rate_limit(CLIENT_ID, DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN)

    other = await check_rate_limit("client-xyz", DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN)
    assert other.allowed is True
    assert fake_redis.keys() == {RATE_KEY, "rate_limit:client:client-xyz"}


async def test_rate_limit_fail_open_on_redis_error(
    broken_redis: None, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger=rate_limit.logger.name):
        result = await check_rate_limit(
            CLIENT_ID, DEFAULT_LIMIT_PER_MINUTE, DEFAULT_LIMIT_PER_10MIN
        )
    assert result.allowed is True
    assert result.degraded is True
    assert result.retry_after_seconds == 0
    messages = [record.getMessage() for record in caplog.records]
    assert any("rate-limit fail-open" in message and CLIENT_ID in message for message in messages)


# ── 連續失敗鎖定 ────────────────────────────────────────────────────────
async def test_four_failures_do_not_lock(fake_redis: FakeRedis) -> None:
    for _ in range(rate_limit.AUTH_FAIL_THRESHOLD - 1):
        state = await register_auth_failure(CLIENT_ID)
        assert state.locked is False
    assert (await check_auth_lock(CLIENT_ID)).locked is False
    assert fake_redis.keys() == {FAIL_KEY}
    assert await fake_redis.ttl(FAIL_KEY) == AUTH_FAIL_TTL_SECONDS


async def test_fifth_failure_locks_for_300_seconds(fake_redis: FakeRedis) -> None:
    for _ in range(rate_limit.AUTH_FAIL_THRESHOLD - 1):
        await register_auth_failure(CLIENT_ID)

    locked = await register_auth_failure(CLIENT_ID)
    assert locked.locked is True
    assert locked.retry_after_seconds == AUTH_LOCK_TTL_SECONDS
    assert locked.degraded is False
    assert fake_redis.keys() == {LOCK_KEY}

    state = await check_auth_lock(CLIENT_ID)
    assert state.locked is True
    assert state.retry_after_seconds == AUTH_LOCK_TTL_SECONDS


async def test_lock_auto_releases_after_ttl(fake_redis: FakeRedis) -> None:
    for _ in range(rate_limit.AUTH_FAIL_THRESHOLD):
        await register_auth_failure(CLIENT_ID)
    assert (await check_auth_lock(CLIENT_ID)).locked is True

    fake_redis.advance(AUTH_LOCK_TTL_SECONDS - 1)
    assert (await check_auth_lock(CLIENT_ID)).locked is True
    assert (await check_auth_lock(CLIENT_ID)).retry_after_seconds == 1

    fake_redis.advance(2)
    assert (await check_auth_lock(CLIENT_ID)).locked is False
    assert fake_redis.keys() == set()


async def test_success_clears_failure_count(fake_redis: FakeRedis) -> None:
    for _ in range(rate_limit.AUTH_FAIL_THRESHOLD - 1):
        await register_auth_failure(CLIENT_ID)
    await clear_auth_failures(CLIENT_ID)
    assert fake_redis.keys() == set()

    # 計數歸零後再失敗 4 次仍不鎖定
    for _ in range(rate_limit.AUTH_FAIL_THRESHOLD - 1):
        state = await register_auth_failure(CLIENT_ID)
        assert state.locked is False
    assert (await check_auth_lock(CLIENT_ID)).locked is False


async def test_failure_count_is_per_client(fake_redis: FakeRedis) -> None:
    for _ in range(rate_limit.AUTH_FAIL_THRESHOLD - 1):
        await register_auth_failure(CLIENT_ID)
    other = await register_auth_failure("client-xyz")
    assert other.locked is False
    assert fake_redis.keys() == {FAIL_KEY, "auth_fail:client:client-xyz"}


async def test_lock_helpers_fail_open_on_redis_error(
    broken_redis: None, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger=rate_limit.logger.name):
        assert (await check_auth_lock(CLIENT_ID)).locked is False
        assert (await check_auth_lock(CLIENT_ID)).degraded is True
        assert (await register_auth_failure(CLIENT_ID)).locked is False
        assert (await register_auth_failure(CLIENT_ID)).degraded is True
        await clear_auth_failures(CLIENT_ID)

    messages = [record.getMessage() for record in caplog.records]
    assert all("rate-limit fail-open" in message for message in messages)
    joined = "\n".join(messages)
    for action in ("check_auth_lock", "register_auth_failure", "clear_auth_failures"):
        assert f"action={action}" in joined
        assert f"client_id={CLIENT_ID}" in joined


# ── 靜態:模組不得碰 DB ─────────────────────────────────────────────────
def test_module_has_no_db_import() -> None:
    source = Path(str(rate_limit.__file__)).read_text(encoding="utf-8")
    imports = [
        line for line in source.splitlines() if line.startswith(("import ", "from "))
    ]
    assert imports
    forbidden = ("repositor", "session", "sqlalchemy", "app.models", "app.core.db")
    for line in imports:
        assert not any(token in line.lower() for token in forbidden), line
