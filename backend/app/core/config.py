from __future__ import annotations

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
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @model_validator(mode="after")
    def _fail_fast_in_prod(self) -> Settings:
        if self.APP_ENV in ("staging", "production"):
            for name, actual, development_default in [
                ("JWT_SECRET_KEY", self.JWT_SECRET_KEY, JWT_SECRET_KEY_DEVELOPMENT_DEFAULT),
            ]:
                if actual == development_default:
                    raise ValueError(f"APP_ENV={self.APP_ENV} 但 {name} 仍為 development 預設值")
        return self


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
