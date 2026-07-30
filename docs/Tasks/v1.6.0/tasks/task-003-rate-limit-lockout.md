---
id: task-003
title: per-Client Rate Limit(雙窗口)+ 連續失敗鎖定(Redis,fail-open)
status: pending
parallel: true
depends_on: [task-002]
affected_files:
  - backend/app/api_client_router/common/rate_limit.py
  - backend/tests/test_api_client_rate_limit.py
estimated_hours: 3
---

## 目標

實作 per-Client 限流(每分鐘 / 每 10 分鐘雙窗口,參數由呼叫端傳入 = DB 值)與 token 端點連續失敗鎖定,計數與鎖定全放 Redis(沿用 `app/core/redis.py` 連線),Redis 故障 fail-open + 告警 log。

## 規格(user 已裁定,不再問)

- **限流 key(user 指定,禁改)**:`rate_limit:client:<client_id>`。
  - 實作:**Redis ZSET 滑動窗口**——單一 key 同時服務兩個窗口:`ZADD`(score=當下 epoch ms)→ `ZREMRANGEBYSCORE` 清 >10 分鐘舊項 → `ZCOUNT` 分別數最近 60s 與 600s;key `EXPIRE 600s` 每次刷新。如此 key 名可完全符合 user 指定格式(不加窗口後綴)。
  - 介面:`async def check_rate_limit(client_id: str, limit_per_minute: int, limit_per_10min: int) -> RateLimitResult`;超限回傳含 `retry_after_seconds`(取較近可用窗口估算,秒向上取整)。
  - 預設值 30 / 200 由呼叫端(task-004 讀 DB)傳入;**本模組不查 DB**。未知 client_id(DB 無此列)呼叫端以預設 30/200 節流,防列舉爆破。
- **連續失敗鎖定**:key `auth_fail:client:<client_id>`(INCR + TTL 15 分鐘)與 `auth_lock:client:<client_id>`(鎖定旗標)。連續 **5** 次驗證失敗(401)→ 鎖定 **300 秒**(TTL 自動解鎖);鎖定中一律回 429 + `Retry-After`(值 = 鎖剩餘 TTL)。成功取證即清除失敗計數。
- **fail-open**:任何 Redis 例外 → 放行 + `logger.error`(訊息含「rate-limit fail-open」與 client_id,走既有結構化 log;禁吞例外不吭聲)。
- 超限 / 鎖定的 HTTP 回應組裝(429 + `Retry-After` header + 統一封套)由 task-004 在端點層完成;本模組只回結構化結果。

## Acceptance

- [ ] `uv run pytest tests/test_api_client_rate_limit.py` 全綠,至少涵蓋:第 30 次通過、第 31 次(60s 窗)被擋且 `retry_after_seconds` > 0;10 分鐘窗第 201 次被擋;窗口滑動後恢復;Redis 中 key 名恰為 `rate_limit:client:<client_id>`(斷言 key 存在且無其他前綴變形);連續 5 次失敗觸發鎖定、TTL 過後自動解鎖;成功後失敗計數歸零;Redis 連線炸掉(monkeypatch 丟例外)→ 放行且 log 有 fail-open 紀錄
- [ ] 限流參數以參數注入,模組內無 DB import(靜態檢查:檔內不得 import repository / session)
- [ ] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤;`uv run pytest` 既有全套全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/08-performance.md`
