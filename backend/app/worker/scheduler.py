"""taskiq scheduler:以自有 DB `schedules` 表為排程來源,到點派工 `run_etl`。

scheduler 啟動指令(與 worker 各自獨立啟動;供 task-012 容器 command 使用):

    uv run taskiq scheduler app.worker.scheduler:scheduler

- 排程來源:`schedules` 表(啟用且未刪除者);停用排程不派工。
- cron 一律以 UTC+8 解讀(00-overview/05-timezone.md)。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy import select
from taskiq import ScheduledTask, ScheduleSource, TaskiqScheduler

import app.worker.tasks  # noqa: F401 — 確保 run_etl 已註冊到 broker
from app.core.db import AsyncSessionLocal
from app.models import Schedule
from app.worker.broker import broker

# cron 一律以 UTC+8 解讀;台灣無 DST,固定 +8 與 Asia/Taipei 等價,
# 且不依賴系統 tzdata(本機 Windows 缺 tzdata 時 ZoneInfo 會 raise,同 engine.TZ_TAIPEI 理由)
CRON_OFFSET_TAIPEI = timedelta(hours=8)

RUN_ETL_TASK_NAME = "run_etl"


def build_scheduled_tasks(schedules: Sequence[Schedule]) -> list[ScheduledTask]:
    """把 DB 排程轉 taskiq ScheduledTask;停用 / 已刪除排程一律不派工。"""
    tasks: list[ScheduledTask] = []
    for schedule in schedules:
        if not schedule.is_enabled or schedule.is_deleted:
            continue
        tasks.append(
            ScheduledTask(
                task_name=RUN_ETL_TASK_NAME,
                labels={},
                args=[],
                kwargs={
                    "trigger_type": "schedule",
                    "schedule_pid": schedule.pid,
                    "etl_table_pid": schedule.etl_table_pid,
                },
                schedule_id=f"schedule-{schedule.pid}",
                cron=schedule.cron_expr,
                cron_offset=CRON_OFFSET_TAIPEI,
            )
        )
    return tasks


class DbScheduleSource(ScheduleSource):
    """自訂 schedule source:每輪自 DB 重讀 `schedules`,啟停即時生效。"""

    async def get_schedules(self) -> list[ScheduledTask]:
        async with AsyncSessionLocal() as session:
            rows = (
                (
                    await session.execute(
                        select(Schedule)
                        .where(
                            Schedule.is_enabled.is_(True),
                            Schedule.is_deleted.is_(False),
                        )
                        .order_by(Schedule.pid)
                    )
                )
                .scalars()
                .all()
            )
        return build_scheduled_tasks(rows)


scheduler = TaskiqScheduler(broker=broker, sources=[DbScheduleSource()])
