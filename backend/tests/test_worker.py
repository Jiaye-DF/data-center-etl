"""worker broker 層測試(不連 redis / 真 DB)。

v1.3.1:config-ETL 的 `run_etl` task 已下線移除;排程派工(mirror_sync 分組)
覆蓋見 `test_scheduler_v131.py`,增量 + tables 偵測覆蓋見 `test_mirror_sync_tables_v131.py`。
本檔僅保留 broker 建立行為:測試環境退 InMemoryBroker;非測試環境缺 REDIS_URL fail-fast。
"""

import os

# app.core.db 於 import 時建立 engine;測試不連 DB,僅需合法 URL 讓 Settings 可載入
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

import pytest  # noqa: E402
from taskiq import InMemoryBroker  # noqa: E402

from app.worker import broker as broker_module  # noqa: E402


def test_broker_falls_back_to_inmemory_under_pytest() -> None:
    assert isinstance(broker_module.broker, InMemoryBroker)


def test_create_broker_fail_fast_without_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_VERSION", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        broker_module.create_broker()
