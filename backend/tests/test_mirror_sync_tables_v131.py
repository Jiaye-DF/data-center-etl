"""mirror_sync v1.3.1 tables 範圍測試(全 fake 注入,不連 redis / 真 DB)。

涵蓋 v1.3.1:
- `_resolve_sync_targets`:tables 指定時只回該清單(且需搭配 schema);全量(皆空)回全來源表。
- incremental=True + tables=[...]:偵測 / 同步範圍限縮於指定表,不觸及清單外的來源表;
  清單內未變動表 skip、變動表同步。
- incremental=False + tables=[...]:忽略偵測整批覆蓋指定表(仍不觸及清單外表)。
- incremental=False 無 tables(人工全量保底):覆蓋全來源表,行為與 v1.3.0 一致。
- mirror_sync 不再讀取逐表排除旗標(排除語意由排程啟停決定)。
"""

from __future__ import annotations

import os

# app.core.db 於 import 時建立 engine;測試不連 DB,僅需合法 URL 讓 Settings 可載入
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

from typing import Any  # noqa: E402

import pytest  # noqa: E402

from app.etl.engine import EtlTableConfig  # noqa: E402
from app.etl.mirror import TableStat  # noqa: E402
from app.worker import tasks  # noqa: E402

# ---------------------------------------------------------------------------
# Fakes(不連 redis / 真 DB)
# ---------------------------------------------------------------------------


class FakeMirror:
    """結構相容 MirrorEngine:計數器可控,mirror_table 記錄被灌表。"""

    def __init__(self, stats: dict[tuple[str, str], TableStat], *, written: int = 3) -> None:
        self._stats = stats
        self._written = written
        self.mirrored: list[tuple[str, str]] = []
        self.disposed = False

    async def list_source_tables(self) -> list[tuple[str, str]]:
        return sorted(self._stats.keys())

    async def fetch_source_stats(self) -> dict[tuple[str, str], TableStat]:
        return dict(self._stats)

    async def mirror_table(self, schema: str, table: str, *, batch_size: int = 1000) -> int:
        self.mirrored.append((schema, table))
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

    def __init__(self, baselines: dict[tuple[str, str], tuple[int, int, int] | None]) -> None:
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
        self.run.update({"status": status, "total_tables": total_tables})


async def _noop_delete_pattern(pattern: str) -> None:
    return None


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mirror: FakeMirror,
    store: FakeRunStore,
    repo: FakeRepo,
) -> None:
    """把 mirror_sync 的所有外部相依換成 fake(不連 redis / 真 DB)。"""
    monkeypatch.setattr(tasks, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(tasks, "make_store", lambda session: store)
    monkeypatch.setattr(tasks, "make_mirror", lambda: mirror)
    monkeypatch.setattr(tasks, "RdsTableMetaRepository", lambda session: repo)
    monkeypatch.setattr(tasks.cache, "delete_pattern", _noop_delete_pattern)


async def _invoke(**kwargs: Any) -> dict[str, Any]:
    task = await tasks.mirror_sync.kiq(**kwargs)
    result = await task.wait_result(timeout=10)
    assert not result.is_err, result.error
    return result.return_value


# ---------------------------------------------------------------------------
# _resolve_sync_targets(純函式:tables / 單表 / 全量分支)
# ---------------------------------------------------------------------------


async def test_resolve_targets_tables_scoped_to_schema() -> None:
    mirror = FakeMirror({("DS", "AAA"): TableStat(1, 0, 0)})
    targets = await tasks._resolve_sync_targets(mirror, "DS", None, ["AAA", "BBB"])
    assert targets == [("DS", "AAA"), ("DS", "BBB")]
    # tables 未觸發全量掃描(list_source_tables 不被使用)
    assert mirror.mirrored == []


async def test_resolve_targets_tables_requires_schema() -> None:
    mirror = FakeMirror({})
    with pytest.raises(ValueError, match="schema"):
        await tasks._resolve_sync_targets(mirror, None, None, ["AAA"])


async def test_resolve_targets_full_returns_all_source_tables() -> None:
    mirror = FakeMirror({("DS", "AAA"): TableStat(1, 0, 0), ("DS", "BBB"): TableStat(1, 0, 0)})
    targets = await tasks._resolve_sync_targets(mirror, None, None, None)
    assert targets == [("DS", "AAA"), ("DS", "BBB")]


# ---------------------------------------------------------------------------
# incremental=True + tables:偵測 / 同步限縮於指定表
# ---------------------------------------------------------------------------


async def test_incremental_tables_scopes_detection_to_listed_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """指定 tables=[AAA, BBB];AAA 變動、BBB 未變動,清單外的 ZZZ 完全不被觸及。"""
    stats = {
        ("DS", "AAA"): TableStat(20, 0, 0),  # baseline 10 → 變動
        ("DS", "BBB"): TableStat(5, 0, 0),  # baseline 5 → 未變動
        ("DS", "ZZZ"): TableStat(99, 0, 0),  # 清單外:不應被偵測 / 同步
    }
    baselines = {
        ("DS", "AAA"): (10, 0, 0),
        ("DS", "BBB"): (5, 0, 0),
        ("DS", "ZZZ"): (1, 0, 0),
    }
    mirror = FakeMirror(stats)
    store = FakeRunStore()
    repo = FakeRepo(baselines)
    _patch(monkeypatch, mirror=mirror, store=store, repo=repo)

    ret = await _invoke(schema="DS", tables=["AAA", "BBB"], incremental=True)

    # 只同步變動且在清單內的 AAA;BBB skip;ZZZ 不在範圍內
    assert mirror.mirrored == [("DS", "AAA")]
    assert repo.signatures == [("DS", "AAA")]
    assert ret["total_tables"] == 2
    assert ret["success_tables"] == 1
    assert ret["skipped_tables"] == 1
    assert ("DS", "ZZZ") not in mirror.mirrored


# ---------------------------------------------------------------------------
# incremental=False + tables:忽略偵測整批覆蓋指定表(仍不觸及清單外)
# ---------------------------------------------------------------------------


async def test_full_sync_tables_ignores_detection_but_stays_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stats = {
        ("DS", "AAA"): TableStat(10, 0, 0),  # baseline==current(全量仍應灌)
        ("DS", "BBB"): TableStat(5, 0, 0),
        ("DS", "ZZZ"): TableStat(1, 0, 0),  # 清單外
    }
    baselines = {("DS", "AAA"): (10, 0, 0), ("DS", "BBB"): (5, 0, 0)}
    mirror = FakeMirror(stats)
    store = FakeRunStore()
    repo = FakeRepo(baselines)
    _patch(monkeypatch, mirror=mirror, store=store, repo=repo)

    ret = await _invoke(schema="DS", tables=["AAA", "BBB"], incremental=False)

    # 全量:清單內兩表皆灌(不看偵測),清單外 ZZZ 不動;signature 仍刷新
    assert mirror.mirrored == [("DS", "AAA"), ("DS", "BBB")]
    assert repo.signatures == [("DS", "AAA"), ("DS", "BBB")]
    assert ret["success_tables"] == 2
    assert ret["skipped_tables"] == 0
    assert ("DS", "ZZZ") not in mirror.mirrored


# ---------------------------------------------------------------------------
# incremental=False 無 tables:人工全量保底,覆蓋全來源表(對齊 v1.3.0)
# ---------------------------------------------------------------------------


async def test_full_sync_without_tables_covers_all_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stats = {
        ("DS", "AAA"): TableStat(10, 0, 0),
        ("DS", "BBB"): TableStat(5, 0, 0),
    }
    mirror = FakeMirror(stats)
    store = FakeRunStore()
    repo = FakeRepo({("DS", "AAA"): (10, 0, 0), ("DS", "BBB"): (5, 0, 0)})
    _patch(monkeypatch, mirror=mirror, store=store, repo=repo)

    ret = await _invoke(incremental=False)

    # 全量無 tables → 走 list_source_tables 全來源表,無異動亦全灌(人工全量保底)
    assert mirror.mirrored == [("DS", "AAA"), ("DS", "BBB")]
    assert ret["total_tables"] == 2
    assert ret["success_tables"] == 2
    assert ret["skipped_tables"] == 0
