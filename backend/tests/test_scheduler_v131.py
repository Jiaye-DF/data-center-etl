"""scheduler v1.3.1 分組派工測試(純函式 build_scheduled_tasks,不連 DB)。

涵蓋 v1.3.1 排程單一化 + 依表分組:
- 讀「啟用、未刪除、有 source_table」的排程;依 (cron_expr, source_schema) 分組,
  同組合併派一發 `mirror_sync(incremental=True, schema=<schema>, tables=[...])`。
- 同 cron 同 schema 的多張表 → 單一派工其 tables 含全部表。
- 同 cron 但跨 schema → 按 schema 拆多發(對齊 mirror_sync tables 需同 schema)。
- 不同 cron → 拆多發。
- 停用 / 已刪除 / 無 source_schema 或 source_table 者不派工。
"""

import os

# app.core.db 於 import 時建立 engine;測試不連 DB,僅需合法 URL 讓 Settings 可載入
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

from datetime import timedelta  # noqa: E402

from app.models import Schedule  # noqa: E402
from app.worker.scheduler import (  # noqa: E402
    CRON_OFFSET_TAIPEI,
    MIRROR_SYNC_TASK_NAME,
    build_scheduled_tasks,
)


def _schedule(
    *,
    pid: int,
    is_enabled: bool = True,
    is_deleted: bool = False,
    cron_expr: str = "0 3 * * *",
    source_schema: str | None = "DS",
    source_table: str | None = "GAT_FILE",
) -> Schedule:
    schedule = Schedule(
        pid=pid,
        name=f"排程-{pid}",
        cron_expr=cron_expr,
        is_enabled=is_enabled,
        source_schema=source_schema,
        source_table=source_table,
    )
    schedule.is_deleted = is_deleted
    return schedule


def test_same_cron_and_schema_merge_into_single_mirror_sync() -> None:
    """同 cron 同 schema 的 3 張啟用表 → 單一 mirror_sync,其 tables 含該 3 表。"""
    scheduled = build_scheduled_tasks(
        [
            _schedule(pid=1, cron_expr="0 2 * * *", source_table="GAT_FILE"),
            _schedule(pid=2, cron_expr="0 2 * * *", source_table="GAM_FILE"),
            _schedule(pid=3, cron_expr="0 2 * * *", source_table="GAQ_FILE"),
        ]
    )

    assert len(scheduled) == 1
    task = scheduled[0]
    assert task.task_name == MIRROR_SYNC_TASK_NAME == "mirror_sync"
    assert task.cron == "0 2 * * *"
    # cron 以 UTC+8 解讀(00-overview/05-timezone.md;台灣無 DST,固定 +8 等價 Asia/Taipei)
    assert task.cron_offset == CRON_OFFSET_TAIPEI == timedelta(hours=8)
    assert task.kwargs == {
        "incremental": True,
        "schema": "DS",
        "tables": ["GAT_FILE", "GAM_FILE", "GAQ_FILE"],
        "trigger_type": "schedule",
    }
    # schedule_id 穩定:cron-<schema>-<正規化 cron>
    assert task.schedule_id == "cron-DS-0_2_*_*_*"


def test_different_cron_dispatched_separately() -> None:
    scheduled = build_scheduled_tasks(
        [
            _schedule(pid=1, cron_expr="0 2 * * *", source_table="GAT_FILE"),
            _schedule(pid=2, cron_expr="0 5 * * *", source_table="GAM_FILE"),
        ]
    )

    assert len(scheduled) == 2
    by_cron = {t.cron: t for t in scheduled}
    assert by_cron["0 2 * * *"].kwargs["tables"] == ["GAT_FILE"]
    assert by_cron["0 5 * * *"].kwargs["tables"] == ["GAM_FILE"]


def test_same_cron_cross_schema_split_by_schema() -> None:
    """同 cron 但跨 schema → 按 schema 拆多發(mirror_sync tables 需同 schema)。"""
    scheduled = build_scheduled_tasks(
        [
            _schedule(pid=1, cron_expr="0 2 * * *", source_schema="DS", source_table="GAT_FILE"),
            _schedule(pid=2, cron_expr="0 2 * * *", source_schema="DS", source_table="GAM_FILE"),
            _schedule(pid=3, cron_expr="0 2 * * *", source_schema="M2201", source_table="M2201"),
        ]
    )

    assert len(scheduled) == 2
    by_schema = {t.kwargs["schema"]: t for t in scheduled}
    assert by_schema["DS"].kwargs["tables"] == ["GAT_FILE", "GAM_FILE"]
    assert by_schema["M2201"].kwargs["tables"] == ["M2201"]
    # 每組 schema 各有穩定且相異的 schedule_id
    assert {t.schedule_id for t in scheduled} == {
        "cron-DS-0_2_*_*_*",
        "cron-M2201-0_2_*_*_*",
    }


def test_disabled_deleted_or_missing_source_not_dispatched() -> None:
    scheduled = build_scheduled_tasks(
        [
            _schedule(pid=1, is_enabled=True, source_table="GAT_FILE"),
            _schedule(pid=2, is_enabled=False, source_table="GAM_FILE"),
            _schedule(pid=3, is_enabled=True, is_deleted=True, source_table="GAQ_FILE"),
            _schedule(pid=4, is_enabled=True, source_table=None),
            _schedule(pid=5, is_enabled=True, source_schema=None, source_table="ORPHAN"),
        ]
    )

    # 只有 pid=1(啟用、未刪除、schema/table 齊全)進入派工
    assert len(scheduled) == 1
    assert scheduled[0].kwargs["tables"] == ["GAT_FILE"]
    assert scheduled[0].kwargs["schema"] == "DS"


def test_all_dispatched_tasks_are_incremental_mirror_sync() -> None:
    scheduled = build_scheduled_tasks(
        [
            _schedule(pid=1, cron_expr="0 2 * * *", source_table="GAT_FILE"),
            _schedule(pid=2, cron_expr="0 5 * * *", source_table="GAM_FILE"),
        ]
    )
    assert all(t.task_name == "mirror_sync" for t in scheduled)
    assert all(t.kwargs["incremental"] is True for t in scheduled)
    assert all(t.kwargs["trigger_type"] == "schedule" for t in scheduled)
    # sync 排程不再帶 etl_table_pid / schedule_pid(改以 tables 分組派工)
    assert all("etl_table_pid" not in t.kwargs for t in scheduled)
    assert all("schedule_pid" not in t.kwargs for t in scheduled)
