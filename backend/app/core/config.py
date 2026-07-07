from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

JWT_SECRET_KEY_DEVELOPMENT_DEFAULT = "changeme-32-bytes-very-very-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "data-center-etl"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DATABASE_URL: str
    JWT_SECRET_KEY: str = Field(default=JWT_SECRET_KEY_DEVELOPMENT_DEFAULT)
    JWT_EXPIRE_MINUTES: int = 480
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
