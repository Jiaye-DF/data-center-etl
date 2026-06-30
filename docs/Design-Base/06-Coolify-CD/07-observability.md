# 07-observability — Log / Metric / 錯誤追蹤

> **何時讀**:設定觀測 / 接 Sentry / 看 production log 才讀。

三層:**Log**(Coolify 內建 stdout 收集)、**Metric**(Coolify 內建 + 可選外接)、**錯誤追蹤 / APM**(Sentry 或同等)。

---

## Log

### 應用層輸出

- 一律 stdout / stderr(**禁**寫檔)— Coolify / docker 自動收
- 結構化 JSON line 格式(對齊 `03-backend/05-exceptions-and-logging.md`)
- 時戳 ISO 8601 + offset(對齊 `00-overview/05-timezone.md`)
- **禁** log 機密(token / cookie 全值 / connection string,對齊 `00-overview/02-secrets.md`)

### Coolify 內查看

Coolify Application → Logs 頁,即時 stream + 搜尋。

### 長期保存(可選)

Coolify 預設僅保留有限期間 logs。長期保存 / 跨 service 集中查詢需外接:

- **Loki + Grafana**(自架)
- 商用:Datadog / Better Stack
- 走 `90-third-party-service/06-monitoring.md` 接

對應 client 寫於 `app/clients/<provider>/`(對齊 `03-backend/06-clients.md`)。

## Metric

### Coolify 內建

Coolify Application → Resources 頁:CPU / Memory / Network 即時。

### 應用層 metric(可選)

需要 RED metrics(Rate / Errors / Duration)→ 接 Prometheus + Grafana 或同等:

- FastAPI:`prometheus-fastapi-instrumentator`(若採用,加進 `01-versions.md`)
- 對外 endpoint:`/metrics`(內網限定;**禁**對外開)

詳細規範屬第三方串接,見 `90-third-party-service/06-monitoring.md`。

## 錯誤追蹤(Sentry)

預設**啟用**(production 必接,staging 可接,development 不接):

```python
# backend/app/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

if settings.SENTRY_DSN:                      # APP_ENV=production / staging 才設
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        traces_sample_rate=0.1,              # 10% trace
        profiles_sample_rate=0.1,
        integrations=[FastApiIntegration()],
        send_default_pii=False,              # 對齊 04-databases/03-passwords-and-pii.md
    )
```

```ts
// frontend
import * as Sentry from "@sentry/react";

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.VITE_APP_ENV,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
  });
}
```

### 規則

- `SENTRY_DSN` / `VITE_SENTRY_DSN` 走 env 注入(對齊 `00-overview/02-secrets.md`,DSN 視為機密)
- `send_default_pii=False`(對齊 PII 隔離,見 `04-databases/03-passwords-and-pii.md`)
- 機密過濾 → 用 `before_send` hook 二次過濾 stack trace(對齊 `00-overview/02-secrets.md § Log / error 過濾`)

## Health check

`GET /api/v1/health`:

```python
@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    # 簡單 DB ping,不查業務邏輯
    await db.execute(text("SELECT 1"))
    return HealthResponse(status="ok", version=settings.APP_VERSION)
```

- 用於 docker / Coolify healthcheck(對齊 `01-compose.md` / `02-dockerfile-backend.md`)
- 回 200 + 簡單 JSON `{status: "ok"}`
- **禁**重操作(查 N 個第三方);健康檢查超過 1s 視為已不健康

## Alert(可選)

關鍵 alert 設於 Sentry / Grafana / 其他:

- error rate 連 5 分 > 1% → page oncall
- response p95 連 5 分 > 1s → warning
- DB connection saturation > 80% → warning
- healthcheck fail → Coolify 自動回滾 + 通知

各專案依風險決定 alert 集合,寫於 `docs/Tasks/v*/` 或專屬 SOP。
