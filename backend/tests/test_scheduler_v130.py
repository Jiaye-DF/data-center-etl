"""scheduler v1.3 派工測試(純函式 build_scheduled_tasks,不連 DB)。

涵蓋 v1.3 排程單一化:所有啟用排程一律派 `mirror_sync` 增量(全表),
不再派舊 `run_etl`、不再帶 `etl_table_pid`;停用 / 已刪除排程不派工。
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
    is_enabled: bool,
    is_deleted: bool = False,
    cron_expr: str = "0 3 * * *",
    etl_table_pid: int | None = None,
) -> Schedule:
    schedule = Schedule(
        pid=pid,
        name=f"排程-{pid}",
        cron_expr=cron_expr,
        is_enabled=is_enabled,
        etl_table_pid=etl_table_pid,
    )
    schedule.is_deleted = is_deleted
    return schedule


def test_enabled_schedule_dispatches_mirror_sync_incremental() -> None:
    # etl_table_pid 給值也應被忽略(sync 排程全表增量,不帶 etl_table_pid)
    scheduled = build_scheduled_tasks(
        [_schedule(pid=7, is_enabled=True, cron_expr="0 4 * * *", etl_table_pid=3)]
    )

    assert len(scheduled) == 1
    task = scheduled[0]
    assert task.task_name == MIRROR_SYNC_TASK_NAME == "mirror_sync"
    assert task.schedule_id == "schedule-7"
    assert task.cron == "0 4 * * *"
    # cron 以 UTC+8 解讀(00-overview/05-timezone.md;台灣無 DST,固定 +8 等價 Asia/Taipei)
    assert task.cron_offset == CRON_OFFSET_TAIPEI == timedelta(hours=8)
    assert task.kwargs == {
        "incremental": True,
        "trigger_type": "schedule",
        "schedule_pid": 7,
    }
    # v1.3:sync 排程不再帶 etl_table_pid
    assert "etl_table_pid" not in task.kwargs


def test_disabled_schedule_not_dispatched() -> None:
    scheduled = build_scheduled_tasks([_schedule(pid=1, is_enabled=False)])
    assert scheduled == []


def test_deleted_schedule_not_dispatched() -> None:
    scheduled = build_scheduled_tasks(
        [_schedule(pid=2, is_enabled=True, is_deleted=True)]
    )
    assert scheduled == []


def test_mixed_schedules_only_enabled_and_not_deleted() -> None:
    scheduled = build_scheduled_tasks(
        [
            _schedule(pid=1, is_enabled=True),
            _schedule(pid=2, is_enabled=False),
            _schedule(pid=3, is_enabled=True, is_deleted=True),
            _schedule(pid=4, is_enabled=True),
        ]
    )

    assert [t.schedule_id for t in scheduled] == ["schedule-1", "schedule-4"]
    assert all(t.task_name == "mirror_sync" for t in scheduled)
    assert all(t.kwargs["incremental"] is True for t in scheduled)
    assert [t.kwargs["schedule_pid"] for t in scheduled] == [1, 4]
