"""權限設定讀取快取層(v1.6.1 task-003)。

權限設定的唯一真身在目標 RDS(propose v1.6.1),本層只加速讀取、不持有真身:

- **cache-aside**:讀取先查 Redis,未命中才回源(`loader`,通常是 RDS 查詢)並回填,
  回填一律帶 TTL 兜底。
- **異動即失效**:寫入端直改 RDS,**於交易 commit 成功後**呼叫 `invalidate*`,
  下一次讀取即為新值;TTL 只是兜底(失效指令掉了 / 回填與失效交錯),非主要機制。
- **降級不失能**:Redis 任何異常(連線失敗 / timeout / 內容毀損)一律吞下並直讀回源,
  log warning 後照常回值(比照 `api_client_router/common/rate_limit.py` 的 fail-open)。
- **禁放機密**:本層只放權限結構;client_secret / token 等明文一律不得進快取。

失效扇出對照(key 集由呼叫端 service 決定,本層只提供機制):

| 異動 | 失效範圍 |
| --- | --- |
| 系統別 / 作業 / 作業範圍 | `invalidate_lists()` + `invalidate_all_effective()`(牽動面廣) |
| 設定檔內容(勾作業 / 授權矩陣)| 反查綁該檔的 Role → 其 Client,`invalidate_clients(*uids)` |
| 特例組內容 | 反查綁該組的 Client,`invalidate_clients(*uids)` |
| Role 指派 / 特例綁定 / 解除 | `invalidate_clients(client_uid)` |

已知並發窗口:讀取回源期間若剛好發生失效,回源端可能把舊值寫回(cache-aside 固有競態),
最長由 TTL 收斂;寫入端恆「先 RDS 成功、後失效」,故不會出現永久舊值。回源不做跨請求
單飛(single-flight):同 key 併發未命中各自回源、結果相同,最差只是多打幾次 RDS,
而 per-Client 限流已把同一 Client 的併發量壓在小數量級。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Final, cast
from uuid import UUID

from pydantic import BaseModel, JsonValue, ValidationError

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# 本層 key 一律 `client_setting:` 前綴(不套 core.redis 的專案 namespace,對齊 rate_limit 慣例)
KEY_PREFIX: Final = "client_setting:"
EFFECTIVE_PREFIX: Final = f"{KEY_PREFIX}effective:"
LIST_PREFIX: Final = f"{KEY_PREFIX}list:"

# TTL 兜底秒數(集中常數,後續可 env 化)
DEFAULT_TTL_SECONDS: Final = 300

# 前綴失效時單次 DEL 的 key 數上限(避免一次送出過長指令)
_DELETE_BATCH_SIZE: Final = 500

# 快取內容解析失敗的哨兵:`None` 是合法 JSON 值,不能拿來表示「未命中」
_DECODE_FAILED: Final = object()


def effective_key(api_client_uid: UUID | str) -> str:
    """單一 API Client 的最終權限 key(`client_setting:effective:<client_uid>`)。"""
    return f"{EFFECTIVE_PREFIX}{api_client_uid}"


def list_key(resource: str, *parts: object) -> str:
    """管理面清單 key(`client_setting:list:<resource>[:<part>...]`)。"""
    return LIST_PREFIX + ":".join([resource, *(str(part) for part in parts)])


def _log_degraded(action: str, target: str) -> None:
    """Redis 異常一律降級,不影響回值;不記快取內容(避免夾帶敏感資料)。"""
    logger.warning(
        "權限快取降級:Redis 異常改直讀回源(action=%s, target=%s)",
        action,
        target,
        exc_info=True,
    )


def _check_ttl(ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds 必須大於 0(禁無 TTL 快取)")


async def _read(key: str) -> str | None:
    """讀快取原文;未命中或 Redis 異常一律回 None(視為未命中)。"""
    try:
        value = await get_redis().get(key)
    except Exception:
        _log_degraded("get", key)
        return None
    return None if value is None else str(value)


async def _write(key: str, payload: str, ttl_seconds: int) -> None:
    """回填快取;Redis 異常吞下(下次讀取再回源即可)。"""
    try:
        await get_redis().set(key, payload, ex=ttl_seconds)
    except Exception:
        _log_degraded("set", key)


def _decode(key: str, raw: str) -> object:
    """解析快取原文;內容毀損視為未命中(回哨兵)。"""
    try:
        parsed: object = json.loads(raw)
    except ValueError:
        logger.warning("權限快取內容非合法 JSON,視為未命中(key=%s)", key)
        return _DECODE_FAILED
    return parsed


def _encode(key: str, value: JsonValue) -> str | None:
    """序列化回填內容;loader 給了非 JSON 結構時只放棄快取(不讓讀取路徑跟著失敗)。"""
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.warning("權限快取回填內容無法 JSON 序列化,略過快取(key=%s)", key, exc_info=True)
        return None


async def get_or_load(
    key: str,
    loader: Callable[[], Awaitable[JsonValue]],
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> JsonValue:
    """cache-aside 讀取:命中回快取值,未命中呼叫 `loader` 回源並回填(帶 TTL)。

    `loader` 回傳值須為 JSON 可表達結構(權限結構為 dict / list / 純量);Redis 不可用時
    等同直呼 `loader`。空值(`None` / `[]` / `{}`)一樣進快取,不會被當成未命中。
    Pydantic 模型請改用 `get_or_load_model`。
    """
    _check_ttl(ttl_seconds)
    cached = await _read(key)
    if cached is not None:
        decoded = _decode(key, cached)
        if decoded is not _DECODE_FAILED:
            return cast(JsonValue, decoded)
    value = await loader()
    payload = _encode(key, value)
    if payload is not None:
        await _write(key, payload, ttl_seconds)
    return value


async def get_or_load_model[ModelT: BaseModel](
    key: str,
    model_type: type[ModelT],
    loader: Callable[[], Awaitable[ModelT]],
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> ModelT:
    """`get_or_load` 的 Pydantic 版:序列化走 `model_dump_json`,命中走 `model_validate_json`。

    快取內容與現行 schema 不符(改版 / 毀損)時視為未命中,回源後以新格式覆寫。
    """
    _check_ttl(ttl_seconds)
    cached = await _read(key)
    if cached is not None:
        try:
            return model_type.model_validate_json(cached)
        except ValidationError:
            logger.warning(
                "權限快取內容不符 %s,視為未命中(key=%s)", model_type.__name__, key
            )
    value = await loader()
    await _write(key, value.model_dump_json(by_alias=True), ttl_seconds)
    return value


async def invalidate(*keys: str) -> None:
    """刪除指定 key(寫入端於 RDS 交易 commit 成功後呼叫);Redis 異常吞下不擋主流程。"""
    if not keys:
        return
    try:
        await get_redis().delete(*keys)
    except Exception:
        _log_degraded("delete", ", ".join(keys))


async def invalidate_prefix(prefix: str) -> None:
    """刪除前綴下全部 key(SCAN 分批 DEL);前綴須落在本層命名空間內,避免誤刪他模組 key。"""
    if not prefix.startswith(KEY_PREFIX):
        raise ValueError(f"失效前綴須以 {KEY_PREFIX} 開頭")
    try:
        client = get_redis()
        batch: list[str] = []
        async for key in client.scan_iter(match=f"{prefix}*"):
            batch.append(str(key))
            if len(batch) >= _DELETE_BATCH_SIZE:
                await client.delete(*batch)
                batch.clear()
        if batch:
            await client.delete(*batch)
    except Exception:
        _log_degraded("scan_delete", prefix)


async def invalidate_clients(*api_client_uids: UUID | str) -> None:
    """失效指定 Client 的最終權限快取(指派 / 綁定 / 設定檔連動異動用)。"""
    await invalidate(*(effective_key(uid) for uid in api_client_uids))


async def invalidate_all_effective() -> None:
    """失效全部 Client 的最終權限快取(作業 / 範圍等牽動面廣的異動用)。"""
    await invalidate_prefix(EFFECTIVE_PREFIX)


async def invalidate_lists() -> None:
    """失效管理面全部清單快取(系統別 / 作業 / 設定檔 / 特例組等清單異動用)。"""
    await invalidate_prefix(LIST_PREFIX)
