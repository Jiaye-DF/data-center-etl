"""per-Client 限流(雙窗口滑動)+ token 端點連續失敗鎖定;Redis 故障一律 fail-open。

- 限流 key 固定 `rate_limit:client:<client_id>`(不加窗口後綴、不套 core.redis 的 namespace
  前綴):單一 ZSET 以 score=epoch ms 同時服務 60s 與 600s 兩個窗口。
- 本模組不查 DB:上限由呼叫端注入(DB 值,未知 client 用本檔預設)。
- 429 / Retry-After 的回應組裝在端點層,本模組只回結構化結果。
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from uuid import uuid4

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# 未知 client_id(DB 無此列)節流用預設值,與 api_client_users 欄位預設一致
DEFAULT_LIMIT_PER_MINUTE = 30
DEFAULT_LIMIT_PER_10MIN = 200

MINUTE_WINDOW_SECONDS = 60
TEN_MINUTE_WINDOW_SECONDS = 600

AUTH_FAIL_THRESHOLD = 5
AUTH_FAIL_TTL_SECONDS = 900
AUTH_LOCK_TTL_SECONDS = 300


def rate_limit_key(client_id: str) -> str:
    return f"rate_limit:client:{client_id}"


def auth_fail_key(client_id: str) -> str:
    return f"auth_fail:client:{client_id}"


def auth_lock_key(client_id: str) -> str:
    return f"auth_lock:client:{client_id}"


@dataclass(frozen=True)
class RateLimitResult:
    """限流判定結果;`window_seconds` 為觸發的窗口長度(未觸發為 0)。"""

    allowed: bool
    retry_after_seconds: int
    limit: int
    window_seconds: int
    degraded: bool


@dataclass(frozen=True)
class AuthLockState:
    """連續失敗鎖定狀態;`retry_after_seconds` 為鎖剩餘秒數。"""

    locked: bool
    retry_after_seconds: int
    degraded: bool


_ALLOWED = RateLimitResult(
    allowed=True, retry_after_seconds=0, limit=0, window_seconds=0, degraded=False
)
_UNLOCKED = AuthLockState(locked=False, retry_after_seconds=0, degraded=False)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _log_fail_open(client_id: str, action: str) -> None:
    logger.error(
        "rate-limit fail-open:Redis 異常放行(action=%s, client_id=%s)",
        action,
        client_id,
        exc_info=True,
    )


def _window_floor_ms(now_ms: int, window_seconds: int) -> int:
    """窗口下界(含):窗口為 (now - window, now],等了 Retry-After 秒後邊界舊筆必離窗。"""
    return now_ms - window_seconds * 1000 + 1


async def _window_retry_after(key: str, now_ms: int, window_seconds: int) -> int:
    """估算窗口內最舊一筆離開窗口所需秒數(向上取整,至少 1 秒)。"""
    window_ms = window_seconds * 1000
    entries = await get_redis().zrangebyscore(
        key, _window_floor_ms(now_ms, window_seconds), now_ms, start=0, num=1, withscores=True
    )
    if not entries:
        return 1
    oldest_ms = float(entries[0][1])
    return max(1, math.ceil((oldest_ms + window_ms - now_ms) / 1000))


async def check_rate_limit(
    client_id: str, limit_per_minute: int, limit_per_10min: int
) -> RateLimitResult:
    """判定是否超過任一窗口上限,放行才計數(AD-134:被拒請求不佔額度,
    Retry-After = 等到窗口 count 降到 limit 以下的秒數);Redis 異常 → 放行 + fail-open log。"""
    key = rate_limit_key(client_id)
    now_ms = _now_ms()
    try:
        client = get_redis()
        await client.zremrangebyscore(key, "-inf", now_ms - TEN_MINUTE_WINDOW_SECONDS * 1000)
        minute_count = int(
            await client.zcount(key, _window_floor_ms(now_ms, MINUTE_WINDOW_SECONDS), now_ms)
        )
        ten_min_count = int(
            await client.zcount(key, _window_floor_ms(now_ms, TEN_MINUTE_WINDOW_SECONDS), now_ms)
        )

        exceeded: list[tuple[int, int]] = []
        if minute_count >= limit_per_minute:
            exceeded.append((MINUTE_WINDOW_SECONDS, limit_per_minute))
        if ten_min_count >= limit_per_10min:
            exceeded.append((TEN_MINUTE_WINDOW_SECONDS, limit_per_10min))
        if not exceeded:
            await client.zadd(key, {f"{now_ms}-{uuid4().hex}": now_ms})
            await client.expire(key, TEN_MINUTE_WINDOW_SECONDS)
            return _ALLOWED

        # 須全部窗口都低於上限才放行 → 多窗口同時超限取最久者(max)
        estimates = [
            (await _window_retry_after(key, now_ms, window), window, limit)
            for window, limit in exceeded
        ]
        retry_after, window_seconds, limit = max(estimates)
        return RateLimitResult(
            allowed=False,
            retry_after_seconds=retry_after,
            limit=limit,
            window_seconds=window_seconds,
            degraded=False,
        )
    except Exception:
        _log_fail_open(client_id, "check_rate_limit")
        return RateLimitResult(
            allowed=True, retry_after_seconds=0, limit=0, window_seconds=0, degraded=True
        )


async def check_auth_lock(client_id: str) -> AuthLockState:
    """檢查是否處於連續失敗鎖定中;Redis 異常 → 視為未鎖定 + fail-open log。"""
    key = auth_lock_key(client_id)
    try:
        client = get_redis()
        if await client.get(key) is None:
            return _UNLOCKED
        ttl = int(await client.ttl(key))
        return AuthLockState(
            locked=True,
            retry_after_seconds=ttl if ttl > 0 else AUTH_LOCK_TTL_SECONDS,
            degraded=False,
        )
    except Exception:
        _log_fail_open(client_id, "check_auth_lock")
        return AuthLockState(locked=False, retry_after_seconds=0, degraded=True)


async def register_auth_failure(client_id: str) -> AuthLockState:
    """記一次驗證失敗;達門檻即上鎖(TTL 自動解鎖)並回鎖定狀態。"""
    fail_key = auth_fail_key(client_id)
    try:
        client = get_redis()
        failures = int(await client.incr(fail_key))
        if failures == 1:
            await client.expire(fail_key, AUTH_FAIL_TTL_SECONDS)
        if failures < AUTH_FAIL_THRESHOLD:
            return _UNLOCKED
        await client.set(auth_lock_key(client_id), "1", ex=AUTH_LOCK_TTL_SECONDS)
        # 計數歸零,鎖過期後重新累計
        await client.delete(fail_key)
        return AuthLockState(
            locked=True, retry_after_seconds=AUTH_LOCK_TTL_SECONDS, degraded=False
        )
    except Exception:
        _log_fail_open(client_id, "register_auth_failure")
        return AuthLockState(locked=False, retry_after_seconds=0, degraded=True)


async def clear_auth_failures(client_id: str) -> None:
    """成功取證後清除失敗計數;Redis 異常 → 不擋流程 + fail-open log。"""
    try:
        await get_redis().delete(auth_fail_key(client_id))
    except Exception:
        _log_fail_open(client_id, "clear_auth_failures")
