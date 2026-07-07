"""engine 共用原語測試(v1.3.1):config-ETL 逐表管線(run_etl)已下線移除,

本檔僅保留 mirror_sync 仍共用的 reader / writer 原語覆蓋:
RDS 連線 URL 組裝(env fail-fast / URL-encode)與欄位型別對映。
"""

import os

# app.core.db 於 import 時建立 engine;測試不連 DB,僅需合法 URL 讓 Settings 可載入
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

import pytest  # noqa: E402

from app.etl.reader import rds_database_url  # noqa: E402
from app.etl.writer import column_sql_type  # noqa: E402

# ---------------------------------------------------------------------------
# 連線 env fail-fast(缺值即 raise,訊息不含值)
# ---------------------------------------------------------------------------


def test_rds_database_url_fail_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("HOST", "PORT", "USER", "PASSWORD", "SOURCE_DB"):
        monkeypatch.delenv(f"AWS_RDS_{key}", raising=False)
    with pytest.raises(RuntimeError, match="AWS_RDS_HOST"):
        rds_database_url("AWS_RDS_SOURCE_DB")


def test_rds_database_url_builds_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_RDS_HOST", "db.local")
    monkeypatch.setenv("AWS_RDS_PORT", "5433")
    monkeypatch.setenv("AWS_RDS_USER", "etl_user")
    monkeypatch.setenv("AWS_RDS_PASSWORD", "p@ss w")
    # 來源/目標共用連線組,僅 database env 不同
    monkeypatch.setenv("AWS_RDS_SOURCE_DB", "erp_migration_test")
    monkeypatch.setenv("AWS_RDS_TARGET_DB", "erp_etl_hub_test")
    url = rds_database_url("AWS_RDS_SOURCE_DB")
    # 帳密 URL-encode 後進 URL;host / port / db 名正確
    assert url == "postgresql+asyncpg://etl_user:p%40ss+w@db.local:5433/erp_migration_test"
    target_url = rds_database_url("AWS_RDS_TARGET_DB")
    assert target_url.endswith("/erp_etl_hub_test")


def test_column_sql_type_mapping() -> None:
    assert column_sql_type("int") == "BIGINT"
    assert column_sql_type("float") == "DOUBLE PRECISION"
    assert column_sql_type("str") == "TEXT"
    assert column_sql_type(None) == "TEXT"
    assert column_sql_type("unknown") == "TEXT"
