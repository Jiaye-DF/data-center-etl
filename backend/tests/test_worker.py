"""worker 層測試(InMemoryBroker,不連 redis / 真 DB)。

涵蓋:enqueue → run 建立且完成後狀態正確、engine 拋例外 run 標 failed
(不留 running 殭屍)、停用排程不產生派工、broker env fail-fast、
排程指定單表的設定過濾。
"""

import os

# app.core.db 於 import 時建立 engine;測試不連 DB,僅需合法 URL 讓 Settings 可載入
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

from collections.abc import Mapping, Sequence  # noqa: E402
from datetime import timedelta  # noqa: E402
from typing import Any, cast  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from taskiq import InMemoryBroker  # noqa: E402

from app.etl.engine import EtlTableConfig  # noqa: E402
from app.etl.transforms import ColumnMapping  # noqa: E402
from app.models import Schedule  # noqa: E402
from app.worker import broker as broker_module  # noqa: E402
from app.worker import tasks  # noqa: E402
from app.worker.scheduler import CRON_OFFSET_TAIPEI, build_scheduled_tasks  # noqa: E402

# ---------------------------------------------------------------------------
# Fakes(結構相容 engine 的 SourceReader / TargetWriter / RunStore Protocol)
# ---------------------------------------------------------------------------


class FakeReader:
    """以 (schema, table) 對照回傳預置列。"""

    def __init__(self, data: dict[tuple[str, str], list[dict[str, Any]]]) -> None:
        self._data = data
        self.calls: list[tuple[str, str]] = []

    async def fetch_rows(
        self, schema: str, table: str, columns: Sequence[str]
    ) -> list[dict[str, Any]]:
        self.calls.append((schema, table))
        rows = self._data.get((schema, table), [])
        return [{col: row.get(col) for col in columns} for row in rows]


class FakeWriter:
    """記錄每次寫入內容供斷言。"""

    def __init__(self) -> None:
        self.writes: list[dict[str, Any]] = []

    async def write_table(
        self,
        *,
        schema: str,
        table: str,
        columns: Sequence[str],
        column_types: Mapping[str, str | None],
        rows: Sequence[Mapping[str, Any]],
        comment_statements: Sequence[str],
    ) -> int:
        self.writes.append({"schema": schema, "table": table, "rows": [dict(r) for r in rows]})
        return len(rows)


class FakeRunStore:
    """in-memory etl_runs / etl_run_logs;可指定 start_table_log 直接炸(模擬引擎外例外)。"""

    def __init__(self, *, fail_on_start_table: bool = False) -> None:
        self.run: dict[str, Any] = {}
        self.logs: list[dict[str, Any]] = []
        self._fail_on_start_table = fail_on_start_table

    async def create_run(self, *, trigger_type: str, schedule_pid: int | None) -> int:
        self.run = {
            "trigger_type": trigger_type,
            "schedule_pid": schedule_pid,
            "status": "running",
        }
        return 1

    async def start_table_log(self, *, run_pid: int, config: EtlTableConfig) -> int:
        if self._fail_on_start_table:
            raise RuntimeError("etl_run_logs 寫入失敗(模擬 DB 掛掉)")
        self.logs.append(
            {"run_pid": run_pid, "source_table": config.source_table, "status": "running"}
        )
        return len(self.logs)

    async def finish_table_log(
        self,
        log_pid: int,
        *,
        status: str,
        row_count: int | None,
        duration_ms: int | None,
        error_message: str | None,
        error_stack: str | None,
    ) -> None:
        self.logs[log_pid - 1].update(
            {"status": status, "row_count": row_count, "error_message": error_message}
        )

    async def add_skipped_log(self, *, run_pid: int, config: EtlTableConfig) -> None:
        self.logs.append(
            {"run_pid": run_pid, "source_table": config.source_table, "status": "skipped"}
        )

    async def finish_run(
        self,
        run_pid: int,
        *,
        status: str,
        total_tables: int,
        success_tables: int,
        failed_tables: int,
        error_message: str | None,
    ) -> None:
        self.run.update(
            {
                "status": status,
                "total_tables": total_tables,
                "success_tables": success_tables,
                "failed_tables": failed_tables,
                "error_message": error_message,
            }
        )


def _gat_config(*, pid: int = 1, is_enabled: bool = True) -> EtlTableConfig:
    return EtlTableConfig(
        etl_table_pid=pid,
        source_schema="DS",
        source_table="GAT_FILE",
        target_schema="DS",
        target_table="GAT_FILE",
        is_enabled=is_enabled,
        mappings=(
            ColumnMapping("GAT_NO", "GAT_NO", "str", "單據編號(主鍵,字串)"),
            ColumnMapping("GAT_QTY", "GAT_QTY", "int", "數量(整數)"),
        ),
    )


def _patch_worker_deps(
    monkeypatch: pytest.MonkeyPatch,
    *,
    store: FakeRunStore,
    reader: FakeReader,
    writer: FakeWriter,
    configs: list[EtlTableConfig],
) -> None:
    """把 tasks 的 factory 全部換成 fake(不連真 DB / RDS)。"""

    def fake_make_store(session: AsyncSession) -> FakeRunStore:
        return store

    async def fake_load_configs(
        session: AsyncSession, etl_table_pid: int | None
    ) -> list[EtlTableConfig]:
        if etl_table_pid is None:
            return configs
        return [c for c in configs if c.etl_table_pid == etl_table_pid]

    monkeypatch.setattr(tasks, "make_store", fake_make_store)
    monkeypatch.setattr(tasks, "load_configs", fake_load_configs)
    monkeypatch.setattr(tasks, "make_reader", lambda: reader)
    monkeypatch.setattr(tasks, "make_writer", lambda: writer)


# ---------------------------------------------------------------------------
# broker:測試環境退 InMemoryBroker;非測試環境缺 REDIS_URL fail-fast
# ---------------------------------------------------------------------------


def test_broker_falls_back_to_inmemory_under_pytest() -> None:
    assert isinstance(broker_module.broker, InMemoryBroker)


def test_create_broker_fail_fast_without_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_VERSION", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        broker_module.create_broker()


# ---------------------------------------------------------------------------
# enqueue → run 建立且完成後狀態正確
# ---------------------------------------------------------------------------


async def test_enqueue_creates_run_and_finishes_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeRunStore()
    reader = FakeReader(
        {("DS", "GAT_FILE"): [{"GAT_NO": " A1 ", "GAT_QTY": "3"}, {"GAT_NO": "A2", "GAT_QTY": "5"}]}
    )
    writer = FakeWriter()
    _patch_worker_deps(
        monkeypatch, store=store, reader=reader, writer=writer, configs=[_gat_config()]
    )

    task = await tasks.run_etl.kiq(trigger_type="schedule", schedule_pid=7)
    result = await task.wait_result(timeout=5)

    assert not result.is_err
    # run 建立時帶入觸發參數,完成後狀態正確收尾
    assert store.run["trigger_type"] == "schedule"
    assert store.run["schedule_pid"] == 7
    assert store.run["status"] == "success"
    assert (store.run["total_tables"], store.run["success_tables"]) == (1, 1)
    assert store.logs[0]["status"] == "success"
    assert store.logs[0]["row_count"] == 2
    # 任務回傳彙總結果(dict,可序列化)
    assert result.return_value["status"] == "success"
    assert result.return_value["run_pid"] == 1
    assert writer.writes[0]["rows"] == [
        {"GAT_NO": "A1", "GAT_QTY": 3},
        {"GAT_NO": "A2", "GAT_QTY": 5},
    ]


async def test_enqueue_with_etl_table_pid_filters_configs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """排程指定單表 → 只跑該表。"""
    store = FakeRunStore()
    reader = FakeReader({("DS", "GAT_FILE"): [{"GAT_NO": "A1", "GAT_QTY": "1"}]})
    writer = FakeWriter()
    _patch_worker_deps(
        monkeypatch,
        store=store,
        reader=reader,
        writer=writer,
        configs=[_gat_config(pid=1), _gat_config(pid=2)],
    )

    task = await tasks.run_etl.kiq(etl_table_pid=1)
    result = await task.wait_result(timeout=5)

    assert not result.is_err
    assert store.run["total_tables"] == 1
    assert len(writer.writes) == 1


# ---------------------------------------------------------------------------
# engine 拋例外 → run 標 failed(不留 running 殭屍)
# ---------------------------------------------------------------------------


async def test_engine_exception_marks_run_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    store = FakeRunStore(fail_on_start_table=True)
    _patch_worker_deps(
        monkeypatch,
        store=store,
        reader=FakeReader({}),
        writer=FakeWriter(),
        configs=[_gat_config()],
    )

    task = await tasks.run_etl.kiq()
    result = await task.wait_result(timeout=5)

    # 任務以錯誤收場,但 run 不留 running 殭屍狀態
    assert result.is_err
    assert store.run["status"] == "failed"
    assert store.run["error_message"] is not None
    assert "etl_run_logs 寫入失敗" in store.run["error_message"]


# ---------------------------------------------------------------------------
# 停用排程不產生派工
# ---------------------------------------------------------------------------


def _schedule(
    *, pid: int, is_enabled: bool, is_deleted: bool = False, etl_table_pid: int | None = None
) -> Schedule:
    schedule = Schedule(
        pid=pid,
        name=f"排程-{pid}",
        cron_expr="0 2 * * *",
        is_enabled=is_enabled,
        etl_table_pid=etl_table_pid,
    )
    schedule.is_deleted = is_deleted
    return schedule


def test_disabled_or_deleted_schedule_not_dispatched() -> None:
    scheduled = build_scheduled_tasks(
        [
            _schedule(pid=1, is_enabled=True),
            _schedule(pid=2, is_enabled=False),
            _schedule(pid=3, is_enabled=True, is_deleted=True),
        ]
    )

    # 只有啟用且未刪除的排程進入派工清單
    assert [t.schedule_id for t in scheduled] == ["schedule-1"]


def test_scheduled_task_carries_cron_utc8_and_trigger_kwargs() -> None:
    scheduled = build_scheduled_tasks([_schedule(pid=9, is_enabled=True, etl_table_pid=3)])

    task = scheduled[0]
    assert task.task_name == "run_etl"
    assert task.cron == "0 2 * * *"
    # cron 以 UTC+8 解讀(00-overview/05-timezone.md;台灣無 DST,固定 +8 等價 Asia/Taipei)
    assert task.cron_offset == timedelta(hours=8)
    assert CRON_OFFSET_TAIPEI == timedelta(hours=8)
    assert task.kwargs == {
        "trigger_type": "schedule",
        "schedule_pid": 9,
        "etl_table_pid": 3,
    }


# ---------------------------------------------------------------------------
# load_configs:單表過濾(直測 tasks.load_configs 的過濾邏輯)
# ---------------------------------------------------------------------------


async def test_load_configs_filters_by_etl_table_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configs = [_gat_config(pid=1), _gat_config(pid=2)]

    async def fake_load_table_configs(session: AsyncSession) -> list[EtlTableConfig]:
        return configs

    monkeypatch.setattr(tasks, "load_table_configs", fake_load_table_configs)
    session = cast(AsyncSession, object())

    assert await tasks.load_configs(session, None) == configs
    assert await tasks.load_configs(session, 2) == [configs[1]]
    assert await tasks.load_configs(session, 99) == []
