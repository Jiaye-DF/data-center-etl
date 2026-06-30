# 01-client-design — Client 結構 + timeout / retry / circuit breaker

> **何時讀**:任何串第三方都讀(無論服務種類)。

統一 client 結構與防禦機制;對應後端入口規則見 `03-backend/06-clients.md`。

---

## 檔案結構

```
app/clients/<service>/
├── __init__.py          # public exports
├── client.py            # 主類 <Service>Client + httpx 整合
├── schemas.py           # Pydantic 第三方 schema(request / response)
├── errors.py            # <Service>Error 與子類
└── README.md            # 該服務 quirk / 已知 bug / 第三方 API 連結
```

## httpx.AsyncClient(lifespan 建立)

```python
# app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.azure_ad_client = AzureAdClient(
        client_id=settings.AZURE_AD_CLIENT_ID,
        tenant_id=settings.AZURE_AD_TENANT_ID,
        secret=settings.AZURE_AD_CLIENT_SECRET,
    )
    yield
    await app.state.azure_ad_client.aclose()
```

```python
# app/clients/azure_ad/client.py
class AzureAdClient:
    def __init__(self, *, client_id: str, tenant_id: str, secret: str) -> None:
        self._http = httpx.AsyncClient(
            base_url="https://login.microsoftonline.com",
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            headers={"User-Agent": "<project>/1.0"},
        )
        self._client_id = client_id
        ...

    async def aclose(self) -> None:
        await self._http.aclose()
```

## Timeout(必設)

```python
httpx.Timeout(
    connect=5.0,     # TCP 連線
    read=30.0,       # 讀回應
    write=10.0,      # 寫 request body
    pool=5.0,        # 從 pool 拿 connection
)
```

- **禁**用預設無 timeout(`Timeout(None)`)— 一個慢 endpoint 可拖垮整個 worker
- read 時間依服務調整(查詢類 30s、批次類 60–120s)
- 觸發 `httpx.TimeoutException` → 轉服務專屬 `<Service>TimeoutError`

## Retry(預設策略)

僅對**冪等**操作(GET / DELETE)retry;POST / PATCH 預設**不** retry(避免重複扣款 / 重複建立)。

```python
import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")

async def retry(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    retriable: tuple[type[Exception], ...] = (httpx.TimeoutException, httpx.NetworkError),
) -> T:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except retriable as e:
            last = e
            if i < attempts - 1:
                await asyncio.sleep(base_delay * (2 ** i))   # 指數退避
    raise last  # type: ignore[misc]
```

- attempts ≤ 3(避免雪崩)
- 退避用指數(0.5s / 1s / 2s),**禁**固定間隔
- 5xx 視情況 retry;4xx **禁** retry(client 錯誤,重試也錯)

## Circuit breaker(可選)

第三方持續掛(連 N 次失敗)→ 暫時開斷路,直接 raise,避免拖垮自身。可用 `circuitbreaker` 套件或自寫:

```python
class CircuitBreaker:
    def __init__(self, threshold: int = 5, recovery: float = 30.0):
        self.threshold = threshold
        self.recovery = recovery
        self.failures = 0
        self.opened_at: float | None = None

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        now = time.monotonic()
        if self.opened_at is not None:
            if now - self.opened_at < self.recovery:
                raise ServiceUnavailableError("circuit open")
            self.opened_at = None  # half-open 試一次
        try:
            result = await fn()
            self.failures = 0
            return result
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = now
            raise
```

- 啟用:第三方關鍵且不穩(SMS / SMTP)
- 不啟用:第三方核心且必須(SSO / payment;掛了寧可整個請求 fail)

## Mock / 測試

對齊 `03-backend/07-testing.md`:

- 測試走 `respx`(mock httpx)或 `httpx.MockTransport`
- **禁**真實打第三方(慢 + 不可重現 + 燒成本)
- 例外:第三方 sandbox 走 staging / e2e
