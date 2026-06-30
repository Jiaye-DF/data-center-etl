# 04-config — Settings + fail-fast + lifespan

> **何時讀**:改 config / 啟動 flow 才讀。

## Lifespan(取代 `on_event`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
```

**禁** `@app.on_event(...)`(已棄用)。

## 啟動 fail-fast

`APP_ENV=development` 帶預設值的敏感配置 → **必**在 `Settings._fail_fast_in_prod` 用 `@model_validator(mode="after")` 統一檢查 — `APP_ENV in ("staging","production")` 仍為 development 預設值即 `raise ValueError`。

`APP_ENV` 值限定 `development` / `staging` / `production`(對齊 `00-overview/03-env-layers.md`),Settings 必驗:

```python
APP_ENV: Literal["development", "staging", "production"]

@model_validator(mode="after")
def _fail_fast_in_prod(self) -> "Settings":
    if self.APP_ENV in ("staging", "production"):
        for name, actual, dev_default in [("JWT_SECRET_KEY", self.JWT_SECRET_KEY, JWT_SECRET_KEY_DEV_DEFAULT)]:
            if actual == dev_default:
                raise ValueError(f"{name} 仍為 development 預設值")
    return self
```

新 secret 配置:加欄位 + 加進 validator 清單 + 同步 `.env*.example`。
