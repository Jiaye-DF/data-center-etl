"""taskiq scheduler:以自有 DB `schedules` 表為排程來源,到點派工 `mirror_sync`(增量)。

scheduler 啟動指令(與 worker 各自獨立啟動;供 task-012 容器 command 使用):

    uv run taskiq scheduler app.worker.scheduler:scheduler

- 排程來源:`schedules` 表(啟用、未刪除且有 `source_table` 者);停用 / 無來源表者不派工。
- v1.3.1 排程單一化:每筆排程對應一張來源表;`build_scheduled_tasks` 依
  `(cron_expr, source_schema)` 分組,同組合併派一發 `mirror_sync` 增量,其 `tables`
  含該組所有來源表(`mirror_sync` 的 `tables` 需搭配同一 `schema`,故按 schema 再分組)。
- cron 一律以 UTC+8 解讀(00-overview/05-timezone.md)。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy import select
from taskiq import ScheduledTask, ScheduleSource, TaskiqScheduler

import app.worker.tasks  # noqa: F401 — 確保 mirror_sync 已註冊到 broker
from app.core.db import AsyncSessionLocal
from app.models import Schedule
from app.worker.broker import broker

# cron 一律以 UTC+8 解讀;台灣無 DST,固定 +8 與 Asia/Taipei 等價,
# 且不依賴系統 tzdata(本機 Windows 缺 tzdata 時 ZoneInfo 會 raise,同 engine.TZ_TAIPEI 理由)
CRON_OFFSET_TAIPEI = timedelta(hours=8)

MIRROR_SYNC_TASK_NAME = "mirror_sync"


def _normalize_cron(cron_expr: str) -> str:
    """把 cron 正規化為穩定 slug(壓縮空白 → 底線),供 schedule_id 使用。"""
    return "_".join(cron_expr.split())


def build_scheduled_tasks(schedules: Sequence[Schedule]) -> list[ScheduledTask]:
    """把 DB 排程轉 taskiq ScheduledTask。

    依 `(cron_expr, source_schema)` 分組,同組合併派一發 `mirror_sync` 增量,
    `tables` 含該組所有來源表(對齊 `_resolve_sync_targets(schema, tables)` 的同 schema 限制)。
    停用 / 已刪除 / 無 `source_schema` 或 `source_table` 的排程不派工。
    """
    groups: dict[tuple[str, str], list[str]] = {}
    order: list[tuple[str, str]] = []
    for schedule in schedules:
        if not schedule.is_enabled or schedule.is_deleted:
            continue
        if schedule.source_schema is None or schedule.source_table is None:
            continue
        key = (schedule.cron_expr, schedule.source_schema)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(schedule.source_table)

    tasks: list[ScheduledTask] = []
    for cron_expr, schema in order:
        tables = groups[(cron_expr, schema)]
        tasks.append(
            ScheduledTask(
                task_name=MIRROR_SYNC_TASK_NAME,
                labels={},
                args=[],
                kwargs={
                    "incremental": True,
                    "schema": schema,
                    "tables": tables,
                    "trigger_type": "schedule",
                },
                schedule_id=f"cron-{schema}-{_normalize_cron(cron_expr)}",
                cron=cron_expr,
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
                            Schedule.source_table.is_not(None),
                        )
                        .order_by(Schedule.pid)
                    )
                )
                .scalars()
                .all()
            )
        return build_scheduled_tasks(rows)


scheduler = TaskiqScheduler(broker=broker, sources=[DbScheduleSource()])
