# 06-monitoring — 觀測 / 錯誤追蹤 client

> **何時讀**:接 Sentry / Datadog / Loki 才讀。對應規則見 `06-Coolify-CD/07-observability.md`。

---

## 工具選擇(擇一,**禁**併存)

| 類型 | 推薦 |
| --- | --- |
| 錯誤追蹤(預設) | **Sentry**(開源 + 商用 SaaS) |
| Log 集中 | Loki + Grafana(自架)/ Datadog Logs |
| Metrics | Prometheus + Grafana / Datadog |
| APM(可選) | Sentry Performance / Datadog APM |

> 同類別**只選一個**。Sentry 已涵蓋錯誤追蹤 + 部分 APM,小專案通常只接 Sentry 就夠。

## Sentry(後端)

```
SENTRY_DSN=https://<key>@o<org>.ingest.sentry.io/<project>     # 機密
SENTRY_ENVIRONMENT=${APP_ENV}
SENTRY_TRACES_SAMPLE_RATE=0.1
```

```python
# app/clients/sentry/setup.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

def init_sentry(dsn: str, env: str, sample_rate: float = 0.1) -> None:
    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        traces_sample_rate=sample_rate,
        profiles_sample_rate=sample_rate,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        send_default_pii=False,                  # 對齊 04-databases/03-passwords-and-pii.md
        before_send=_filter_sensitive,           # 二次過濾
    )

def _filter_sensitive(event: dict, hint: dict) -> dict | None:
    # 過濾 stack trace 中的 secret / token / cookie
    return event
```

於 `app/main.py`:

```python
if settings.SENTRY_DSN and settings.APP_ENV in ("staging", "production"):
    init_sentry(settings.SENTRY_DSN, settings.APP_ENV, settings.SENTRY_TRACES_SAMPLE_RATE)
```

## Sentry(前端)

```ts
// frontend/src/main.tsx
import * as Sentry from "@sentry/react";

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.VITE_APP_ENV,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({ maskAllText: true, blockAllMedia: true }),  // PII 隱私
    ],
    replaysSessionSampleRate: 0.01,
    replaysOnErrorSampleRate: 1.0,
  });
}
```

對齊 `02-frontend/03-env-and-auth.md` 規則:DSN 走 `VITE_SENTRY_DSN`(可進 bundle,但 DSN 本身曝光不致命)。

## 規則

- `traces_sample_rate ≤ 0.1`(完整 trace 燒錢,1.0 只在 development)
- `send_default_pii=False`(預設關;PII 隔離,對齊 `04-databases/03-passwords-and-pii.md`)
- `before_send` 二次過濾敏感資料(對齊 `00-overview/02-secrets.md § Log / error 過濾`)
- staging / production 啟用;development 關(避免 noise + 燒額度)

## Datadog / Loki(可選)

非預設;若選用則:
- 對應 client 寫於 `app/clients/<provider>/`
- env 命名 `DATADOG_*` / `LOKI_*`
- 加進 `00-overview/01-versions.md` 套件清單

## 對應規則

- 機密 / PII 過濾 → `00-overview/02-secrets.md` / `04-databases/03-passwords-and-pii.md`
- 結構化 log 格式 → `03-backend/05-exceptions-and-logging.md`
- alert 閾值 / 預警 → `06-Coolify-CD/07-observability.md`
