"""mirror_sync 表級平行同步測試(全 fake 注入,不連 redis / 真 RDS / 真 DB)。

涵蓋 task-001:
- 併發度 > 1:同輪多表併發鏡像,實測併發峰值達 SYNC_CONCURRENCY;全部表各恰一筆 log、
  run 統計(total / success / failed)正確。
- 任一表失敗整輪 failed,其餘表照跑(單表失敗不中斷)。
- SYNC_CONCURRENCY=1:行為(含 log 順序)等同現行序列版,併發峰值為 1。
- 增量 skip 表不進併發池:未變動表寫 skip log 但不進 mirror,不占併發名額。

風格對齊 tests/test_mirror_sync_tables_v131.py(fake mirror 記錄併發峰值 / 完成表集合)。
"""

from __future__ import annotations

import asyncio
import os

# app.core.db 於 import 時建立 engine;測試不連 DB,僅需合法 URL 讓 Settings 可載入
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

from typing import Any  # noqa: E402

import pytest  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.etl.engine import EtlTableConfig  # noqa: E402
from app.etl.mirror import TableStat  # noqa: E402
from app.worker import tasks  # noqa: E402

# ---------------------------------------------------------------------------
# Fakes(不連 redis / 真 DB / 真 RDS)
# ---------------------------------------------------------------------------


class FakeMirror:
    """結構相容 MirrorEngine:記錄併發峰值 / 完成表集合;可指定失敗表。

    mirror_table 內以 asyncio.sleep 製造實際掛起,讓多表得以同時在飛行中,
    藉此觀測真正的併發峰值(而非 fake 同步跑完不 yield 的假象)。
    """

    def __init__(
        self,
        stats: dict[tuple[str, str], TableStat],
        *,
        written: int = 3,
        fail_tables: set[tuple[str, str]] | None = None,
        delay: float = 0.02,
    ) -> None:
        self._stats = stats
        self._written = written
        self._fail_tables = fail_tables or set()
        self._delay = delay
        self.mirrored: list[tuple[str, str]] = []
        self._active = 0
        self.peak = 0
        self.disposed = False

    async def list_source_tables(self) -> list[tuple[str, str]]:
        return sorted(self._stats.keys())

    async def fetch_source_stats(self) -> dict[tuple[str, str], TableStat]:
        return dict(self._stats)

    async def mirror_table(self, schema: str, table: str, *, batch_size: int = 1000) -> int:
        self._active += 1
        self.peak = max(self.peak, self._active)
        self.mirrored.append((schema, table))
        try:
            await asyncio.sleep(self._delay)
            if (schema, table) in self._fail_tables:
                raise RuntimeError(f"boom:{schema}.{table}")
        finally:
            self._active -= 1
        return self._written

    async def dispose(self) -> None:
        self.disposed = True


class FakeSession:
    """最小 async session:execute / flush / rollback 皆 noop(mirror_sync 不查真 DB)。"""

    async def execute(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False


class FakeRepo:
    """結構相容 RdsTableMetaRepository:signature 基準可控,mark / update 僅記錄。"""

    def __init__(
        self, baselines: dict[tuple[str, str], tuple[int, int, int] | None]
    ) -> None:
        self._baselines = baselines
        self.synced: list[tuple[str, str]] = []
        self.signatures: list[tuple[str, str]] = []

    async def read_stat_baselines(
        self, dataset: Any
    ) -> dict[tuple[str, str], tuple[int, int, int] | None]:
        return dict(self._baselines)

    async def mark_synced(
        self, dataset: Any, schema: str, table: str, *, actor_uid: Any
    ) -> None:
        self.synced.append((schema, table))

    async def mark_transformed(
        self, dataset: Any, schema: str, table: str, *, actor_uid: Any
    ) -> None:
        return None

    async def update_stat_signature(
        self,
        dataset: Any,
        schema: str,
        table: str,
        *,
        n_tup_ins: int,
        n_tup_upd: int,
        n_tup_del: int,
        actor_uid: Any,
    ) -> None:
        self.signatures.append((schema, table))


class FakeRunStore:
    """in-memory etl_runs / etl_run_logs;記錄逐表 log 狀態供斷言。"""

    def __init__(self) -> None:
        self.run: dict[str, Any] = {}
        self.logs: list[dict[str, Any]] = []

    async def create_run(
        self, *, trigger_type: str, schedule_pid: int | None, total_tables: int
    ) -> int:
        self.run = {
            "trigger_type": trigger_type,
            "schedule_pid": schedule_pid,
            "status": "running",
            "total_tables": total_tables,
        }
        return 1

    async def start_table_log(self, *, run_pid: int, config: EtlTableConfig) -> int:
        self.logs.append({"table": config.source_table, "status": "running"})
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
        self.logs[log_pid - 1].update({"status": status, "row_count": row_count})

    async def add_skipped_log(self, *, run_pid: int, config: EtlTableConfig) -> None:
        self.logs.append({"table": config.source_table, "status": "skipped"})

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
            }
        )


async def _noop_delete_pattern(pattern: str) -> None:
    return None


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mirror: FakeMirror,
    store: FakeRunStore,
    repo: FakeRepo,
    concurrency: int,
) -> None:
    """把 mirror_sync 的所有外部相依換成 fake,並以 env 設定併發度(清快取生效)。"""
    monkeypatch.setattr(tasks, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(tasks, "make_store", lambda session: store)
    monkeypatch.setattr(tasks, "make_mirror", lambda: mirror)
    monkeypatch.setattr(tasks, "RdsTableMetaRepository", lambda session: repo)
    # tasks 以 `from app.core import redis as cache` 引入 → 直接 patch 來源模組屬性
    monkeypatch.setattr("app.core.redis.delete_pattern", _noop_delete_pattern)
    monkeypatch.setenv("SYNC_CONCURRENCY", str(concurrency))
    # conftest 於測試前已清快取;此處設 env 後再清一次,確保 mirror_sync 讀到本測試的併發度
    get_settings.cache_clear()


async def _invoke(
    *,
    schema: str | None = None,
    tables: list[str] | None = None,
    incremental: bool = False,
) -> dict[str, Any]:
    task = await tasks.mirror_sync.kiq(
        schema=schema, tables=tables, incremental=incremental
    )
    result = await task.wait_result(timeout=10)
    assert not result.is_err, result.error
    ret: dict[str, Any] = result.return_value
    return ret


def _log_status_by_table(store: FakeRunStore) -> dict[str, str]:
    """回傳 {table: status};順帶確保每表恰一筆 log(重複表會在此被發現)。"""
    seen: dict[str, str] = {}
    for entry in store.logs:
        table = entry["table"]
        assert table not in seen, f"表 {table} 出現多筆 log"
        seen[table] = entry["status"]
    return seen


def _stats_for(tables: list[str]) -> dict[tuple[str, str], TableStat]:
    return {("DS", t): TableStat(1, 0, 0) for t in tables}


# ---------------------------------------------------------------------------
# 併發度 > 1:多表併發、峰值達併發度、各表恰一筆 log、run 統計正確
# ---------------------------------------------------------------------------


async def test_parallel_reaches_concurrency_and_logs_each_table_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = [f"T{i}" for i in range(6)]
    mirror = FakeMirror(_stats_for(names))
    store = FakeRunStore()
    repo = FakeRepo({})
    _patch(monkeypatch, mirror=mirror, store=store, repo=repo, concurrency=3)

    ret = await _invoke(schema="DS", tables=names, incremental=False)

    # 併發峰值達設定併發度(證實確有平行,非序列)
    assert mirror.peak == 3
    # 完成表集合 = 全部指定表,且各恰一筆
    assert set(mirror.mirrored) == {("DS", n) for n in names}
    assert len(mirror.mirrored) == len(names)
    statuses = _log_status_by_table(store)
    assert statuses == {n: "success" for n in names}
    # run 統計正確
    assert ret["total_tables"] == 6
    assert ret["success_tables"] == 6
    assert ret["failed_tables"] == 0
    assert ret["skipped_tables"] == 0
    assert ret["status"] == "success"
    assert store.run["status"] == "success"


# ---------------------------------------------------------------------------
# 任一表失敗整輪 failed,其餘表照跑
# ---------------------------------------------------------------------------


async def test_one_table_fails_others_still_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = ["T0", "T1", "T2", "T3"]
    mirror = FakeMirror(_stats_for(names), fail_tables={("DS", "T2")})
    store = FakeRunStore()
    repo = FakeRepo({})
    _patch(monkeypatch, mirror=mirror, store=store, repo=repo, concurrency=3)

    ret = await _invoke(schema="DS", tables=names, incremental=False)

    # 失敗表不中斷:全部表都被嘗試鏡像
    assert set(mirror.mirrored) == {("DS", n) for n in names}
    statuses = _log_status_by_table(store)
    assert statuses["T2"] == "failed"
    assert statuses["T0"] == statuses["T1"] == statuses["T3"] == "success"
    # 成功表才更新 signature 基準;失敗表不更新
    assert ("DS", "T2") not in repo.signatures
    assert set(repo.signatures) == {("DS", "T0"), ("DS", "T1"), ("DS", "T3")}
    # run 總狀態 failed
    assert ret["status"] == "failed"
    assert ret["success_tables"] == 3
    assert ret["failed_tables"] == 1
    assert store.run["status"] == "failed"


# ---------------------------------------------------------------------------
# SYNC_CONCURRENCY=1:行為(含 log 順序)等同序列版,峰值為 1
# ---------------------------------------------------------------------------


async def test_concurrency_one_is_serial(monkeypatch: pytest.MonkeyPatch) -> None:
    names = ["A", "B", "C", "D"]
    mirror = FakeMirror(_stats_for(names))
    store = FakeRunStore()
    repo = FakeRepo({})
    _patch(monkeypatch, mirror=mirror, store=store, repo=repo, concurrency=1)

    ret = await _invoke(schema="DS", tables=names, incremental=False)

    # 併發度 1 → 全程僅一表在飛行;鏡像 / log 順序皆等於派發順序(序列語意)
    assert mirror.peak == 1
    assert mirror.mirrored == [("DS", n) for n in names]
    assert [entry["table"] for entry in store.logs] == names
    assert ret["success_tables"] == 4
    assert ret["failed_tables"] == 0
    assert ret["status"] == "success"


# ---------------------------------------------------------------------------
# 增量 skip 表不進併發池
# ---------------------------------------------------------------------------


async def test_incremental_skip_tables_not_in_parallel_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = ["CH0", "SK0", "CH1", "SK1"]
    stats = {
        ("DS", "CH0"): TableStat(20, 0, 0),  # baseline 10 → 變動
        ("DS", "SK0"): TableStat(5, 0, 0),  # baseline 5 → 未變動 → skip
        ("DS", "CH1"): TableStat(30, 0, 0),  # baseline 10 → 變動
        ("DS", "SK1"): TableStat(7, 0, 0),  # baseline 7 → 未變動 → skip
    }
    baselines: dict[tuple[str, str], tuple[int, int, int] | None] = {
        ("DS", "CH0"): (10, 0, 0),
        ("DS", "SK0"): (5, 0, 0),
        ("DS", "CH1"): (10, 0, 0),
        ("DS", "SK1"): (7, 0, 0),
    }
    mirror = FakeMirror(stats)
    store = FakeRunStore()
    repo = FakeRepo(baselines)
    _patch(monkeypatch, mirror=mirror, store=store, repo=repo, concurrency=3)

    ret = await _invoke(schema="DS", tables=names, incremental=True)

    # skip 表不進併發池 → 只有變動表被鏡像;併發峰值不超過變動表數
    assert set(mirror.mirrored) == {("DS", "CH0"), ("DS", "CH1")}
    assert mirror.peak <= 2
    statuses = _log_status_by_table(store)
    assert statuses == {
        "CH0": "success",
        "CH1": "success",
        "SK0": "skipped",
        "SK1": "skipped",
    }
    assert ret["total_tables"] == 4
    assert ret["success_tables"] == 2
    assert ret["skipped_tables"] == 2
    assert ret["failed_tables"] == 0
