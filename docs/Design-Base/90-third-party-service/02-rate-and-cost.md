# 02-rate-and-cost — Rate limit + 成本

> **何時讀**:第三方有 rate limit / 計費(LLM / SMS / payment)才讀。

---

## Client 端 throttle

第三方 rate limit(例:Azure AD 600 req/min、SendGrid 100 emails/sec、OpenAI 10k TPM)時,**先**在自己 client 限速,**禁**等被打 429 才知道。

```python
import asyncio
from collections import deque
from time import monotonic

class TokenBucket:
    def __init__(self, rate: float, capacity: int) -> None:
        self.rate = rate           # tokens / sec
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last = monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens < 1:
                wait = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait)
                self.tokens = 0
            else:
                self.tokens -= 1
```

```python
class SendGridClient:
    def __init__(self) -> None:
        self._bucket = TokenBucket(rate=80, capacity=100)   # 留 20% buffer

    async def send(self, ...) -> None:
        await self._bucket.acquire()
        ...
```

## 429 處理

被打 429 → respect `Retry-After` header,**禁**立即重試:

```python
if response.status_code == 429:
    retry_after = float(response.headers.get("Retry-After", "1"))
    await asyncio.sleep(retry_after)
    raise <Service>RateLimitError(f"rate limited, retry after {retry_after}s")
```

## API cost log

按請求計費的服務(LLM / SMS / payment / 第三方 API)→ 必 log 成本:

```python
logger.info(
    "third_party_call",
    extra={
        "service": "openai",
        "endpoint": "/v1/chat/completions",
        "tokens_in": prompt_tokens,
        "tokens_out": completion_tokens,
        "cost_usd": estimated_cost,
        "user_uid": str(user.uid),
    },
)
```

對齊 `03-backend/05-exceptions-and-logging.md`(結構化 log)。下游可用 log aggregator 出月報。

## 預警閾值

寫入 alert 規則(對齊 `06-Coolify-CD/07-observability.md`):

| 服務 | 閾值 | 行為 |
| --- | --- | --- |
| LLM | 月成本 > 預算 80% | warning;> 100% block |
| SMS / Email | 日量 > 預期 200% | warning(可能漏迴圈) |
| Payment | 失敗率連 5 分 > 5% | page oncall |
| 任意 | 429 比例 > 10% / 小時 | warning,評估升 plan |

預算 / 閾值寫於各 client 的 `README.md`,reflect 時重檢。

## 預算保護

關鍵服務(LLM)加 hard cap,超過直接 raise,避免 runaway:

```python
class OpenAIClient:
    async def complete(self, ...) -> str:
        monthly_spend = await self._cost_repo.get_month_spend()
        if monthly_spend > settings.OPENAI_MONTHLY_BUDGET_USD:
            raise OpenAIBudgetExceededError(f"monthly budget exceeded: ${monthly_spend}")
        ...
```

- 閾值走 env(`OPENAI_MONTHLY_BUDGET_USD`),user 可即時調
- 超預算寫 `fixed.md`(分析 root cause:bug / 業務量真的爆了)
