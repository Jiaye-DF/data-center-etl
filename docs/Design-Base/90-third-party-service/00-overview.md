# 00-overview — 第三方服務治理

> **永遠讀**:任何串第三方任務都必遵守的「治理底線」(命名 / 集中位置 / 錯誤轉換契約)。具體服務範本見對應子檔。

---

## 集中位置(永遠遵守)

第三方串接**僅**寫於 `app/clients/<service>/`,依服務分子目錄:

```
app/clients/
├── azure_ad/
│   ├── __init__.py
│   ├── client.py            # 主要 client 實作
│   ├── schemas.py           # 第三方 request / response schema
│   ├── errors.py            # 服務專屬錯誤類
│   └── README.md            # 該服務的內部文件 / quirk 紀錄
├── smtp/
├── stripe/
└── sentry/
```

**禁**在 `services/` / `api/` 直接 `httpx.get(...)` / SDK 直呼(對齊 `03-backend/06-clients.md`)。

## 命名(永遠遵守)

- 模組:`app/clients/<service-snake-case>/`(例:`azure_ad`、`stripe`、`smtp`)
- 主類:`<Service>Client`(例:`AzureAdClient`)
- 錯誤類:`<Service>Error`(例:`AzureAdError`)+ 子類(例:`AzureAdAuthError`)
- 設定:走 `Settings`(對齊 `03-backend/04-config.md`),命名 `<SERVICE>_<KIND>`(例:`AZURE_AD_CLIENT_ID`、`SMTP_HOST`)

## 錯誤轉換契約(永遠遵守)

第三方錯誤**必**轉成 app 內部錯誤;**禁**讓第三方原始 exception 流到 service / api 層:

```python
# app/clients/azure_ad/client.py
class AzureAdError(AppError): ...
class AzureAdAuthError(AzureAdError): ...
class AzureAdTimeoutError(AzureAdError): ...

class AzureAdClient:
    async def get_user(self, uid: str) -> AzureAdUser:
        try:
            response = await self._http.get(...)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise AzureAdTimeoutError("Azure AD 逾時") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AzureAdAuthError("Azure AD 認證失敗") from e
            raise AzureAdError(f"Azure AD 錯誤:{e.response.status_code}") from e
        return AzureAdUser.model_validate(response.json())
```

- service / api 層**只**catch app 內部錯誤(`AppError` 子類),**禁** catch `httpx.*` / SDK 原生
- 第三方 SDK 也須包裹(SDK exception → 我方錯誤類)

## httpx 共用原則(永遠遵守)

對齊 `03-backend/06-clients.md`:

- 用 `httpx.AsyncClient`,於 FastAPI `lifespan` 建立 + dispose
- 連線池單例,**禁**每 request 開新 client
- 必設 `timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)`(具體值依服務調整)
- retry / circuit breaker 走 `01-client-design.md`

## 機密管理

對齊 `00-overview/02-secrets.md` + `06-Coolify-CD/04-env-and-secrets.md`:

- API key / token / webhook secret 走 env 注入
- **禁**寫進程式碼 / image
- staging / production 機密**獨立**生成

## 子章節

- `01-client-design.md` — clients 結構 + timeout / retry / circuit breaker(任何串接都讀)
- `02-rate-and-cost.md` — rate limit + cost log + 預警
- `03-smtp.md` — SMTP / 信件範本
- `04-sso-azure-ad.md` — 直連 Azure AD SSO(App 自己當 OAuth client)
- `05-payment.md` — Stripe / 綠界 + webhook 簽章
- `06-monitoring.md` — Sentry / Datadog / Loki
- `07-lint-bot.md` — Lint bot / reviewdog / codecov
- `08-df-sso.md` — 串公司 DF-SSO 中央登入器(實際落檔走 `sso-init` skill)
