from __future__ import annotations

from functools import lru_cache
from typing import Literal

from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

JWT_SECRET_KEY_DEVELOPMENT_DEFAULT = "changeme-32-bytes-very-very-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "data-center-etl"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DATABASE_URL: str
    # DB 連線池:多 uvicorn worker 為多行程,每行程各一組池 → 單一行程可用連線上限
    # = DB_POOL_SIZE + DB_MAX_OVERFLOW;整體須滿足
    #   (UVICORN_WORKERS × 每行程上限) + worker + scheduler < postgres max_connections。
    # 部署以 env 依 worker 數下調,避免連線耗盡(見 .env.*.example 說明)。
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    # 單輪同步的表級併發度(僅 worker 讀):同輪多表以 asyncio 併發鏡像,預設 2。
    # 調高 → 來源 RDS 讀壓上升;來源異常時設回 1 退化為序列同步(見 .env.*.example 說明)。
    SYNC_CONCURRENCY: int = 2
    JWT_SECRET_KEY: str = Field(default=JWT_SECRET_KEY_DEVELOPMENT_DEFAULT)
    JWT_EXPIRE_MINUTES: int = 480
    # 對外 API Client 短效 JWT 的簽章密鑰(/api/client):必填、無預設值、至少 32 字元
    # (缺值或過短即 Settings 驗證失敗 fail-fast;禁寫死預設值進版控)
    CLIENT_JWT_SECRET: str = Field(min_length=32)
    # client_secret 可逆加密金鑰(Fernet key,44 字元 urlsafe base64):必填、無預設值
    # 產生:python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # 換金鑰會使既有加密明文無法解密(僅影響儀表板檢視,token 驗證走 bcrypt 不受影響)
    CLIENT_SECRET_ENCRYPTION_KEY: str = Field(min_length=44)
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    # 初始管理員帳密:必填、無預設值(缺 env 即 Settings 驗證失敗 fail-fast,禁預設帳密)
    INIT_ADMIN_USERNAME: str
    INIT_ADMIN_PASSWORD: str
    # DF-SSO 中央登入器(90-third-party-service/08-df-sso.md;IT 發放後由 env 注入,禁硬編)
    SSO_URL: str = ""
    SSO_APP_ID: str = ""
    SSO_APP_SECRET: str = ""
    # 前端對外 origin(SSO callback / logout 的 redirect 落點)
    FRONTEND_URL: str = "http://localhost:3000"
    # Cookie Domain:跨子網域共用登入 cookie 用(例:.zerozero.tw 讓所有 *.zerozero.tw 都收得到)。
    # 留空 = host-only(本機開發預設,cookie 綁單一 host);部署跨二級子網域時必填。
    COOKIE_DOMAIN: str = ""

    @field_validator("CLIENT_SECRET_ENCRYPTION_KEY")
    @classmethod
    def _validate_fernet_key(cls, value: str) -> str:
        # 啟動即驗金鑰合法性(AD-137):長度對但非合法 Fernet key 會延遲到首次加密才爆
        try:
            Fernet(value.encode("ascii"))
        except Exception as exc:
            # 訊息禁含 key 內容(機密)
            raise ValueError("CLIENT_SECRET_ENCRYPTION_KEY 非合法 Fernet 金鑰") from exc
        return value

    @model_validator(mode="after")
    def _fail_fast_in_prod(self) -> Settings:
        if self.APP_ENV in ("staging", "production"):
            for name, actual, development_default in [
                ("JWT_SECRET_KEY", self.JWT_SECRET_KEY, JWT_SECRET_KEY_DEVELOPMENT_DEFAULT),
            ]:
                if actual == development_default:
                    raise ValueError(f"APP_ENV={self.APP_ENV} 但 {name} 仍為 development 預設值")
        return self


@lru_cache
def get_settings() -> Settings:
    # 每請求重新實例化會重讀 .env 檔(scan AD-007)→ 程序內快取;
    # 測試改 env 後以 get_settings.cache_clear() 重置(tests/conftest.py 已統一處理)
    return Settings()  # type: ignore[call-arg]
