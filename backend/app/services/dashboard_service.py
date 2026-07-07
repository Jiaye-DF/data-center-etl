"""總覽儀表板聚合服務:一次組出同步健康 / 待處理失敗表 / 排程概況 / 資料規模。

全讀自有 DB(etl_runs / etl_run_logs / schedules / rds_table_meta),不即時打 RDS。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rds_table_meta import Dataset
from app.repositories.rds_table_meta_repo import RdsTableMetaRepository
from app.repositories.run_repo import RunRepository
from app.repositories.schedule_repo import ScheduleRepository
from app.schemas.dashboard import (
    DashboardDatasetScale,
    DashboardFailedTable,
    DashboardLatestRun,
    DashboardOverview,
    DashboardPendingFailures,
    DashboardSchedules,
    DashboardSyncHealth,
)

# 近況統計視窗 / 失敗表清單封頂(儀表板僅概覽,詳情走執行紀錄頁)
_RECENT_RUN_LIMIT = 20
_FAILED_ITEMS_LIMIT = 20


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self._runs = RunRepository(db)
        self._schedules = ScheduleRepository(db)
        self._meta = RdsTableMetaRepository(db)

    async def overview(self) -> DashboardOverview:
        return DashboardOverview(
            sync_health=await self._sync_health(),
            pending_failures=await self._pending_failures(),
            schedules=await self._schedule_overview(),
            datasets=await self._dataset_scales(),
        )

    async def _sync_health(self) -> DashboardSyncHealth:
        latest = await self._runs.latest_run()
        total, success, failed = await self._runs.recent_run_stats(_RECENT_RUN_LIMIT)
        latest_dto = (
            None
            if latest is None
            else DashboardLatestRun(
                uid=latest.uid,
                trigger_type=latest.trigger_type,
                status=latest.status,
                total_tables=latest.total_tables,
                success_tables=latest.success_tables,
                failed_tables=latest.failed_tables,
                finished_at=latest.finished_at,
            )
        )
        return DashboardSyncHealth(
            latest_run=latest_dto,
            recent_total=total,
            recent_success=success,
            recent_failed=failed,
        )

    async def _pending_failures(self) -> DashboardPendingFailures:
        """最新一筆 run 若有失敗表 → 列其失敗逐表 log(封頂);否則空(視為無待處理)。"""
        latest = await self._runs.latest_run()
        if latest is None or latest.failed_tables <= 0:
            return DashboardPendingFailures(run_uid=None, items=[])
        logs, _ = await self._runs.list_logs(
            etl_run_pid=latest.pid,
            offset=0,
            limit=_FAILED_ITEMS_LIMIT,
            status="failed",
        )
        return DashboardPendingFailures(
            run_uid=latest.uid,
            items=[
                DashboardFailedTable(
                    source_schema=log.source_schema,
                    source_table=log.source_table,
                    error_message=log.error_message,
                )
                for log in logs
            ],
        )

    async def _schedule_overview(self) -> DashboardSchedules:
        summaries = await self._schedules.list_schema_summaries()
        table_total = sum(table_count for _, table_count, _ in summaries)
        enabled_count = sum(enabled_count for _, _, enabled_count in summaries)
        cron_exprs = await self._schedules.enabled_cron_exprs()
        return DashboardSchedules(
            enabled_count=enabled_count,
            table_total=table_total,
            enabled_cron_exprs=cron_exprs,
        )

    async def _dataset_scales(self) -> list[DashboardDatasetScale]:
        scales: list[DashboardDatasetScale] = []
        for dataset in (Dataset.SOURCE, Dataset.TARGET):
            total, nonempty, empty, snap, synced = await self._meta.dataset_scale(
                dataset
            )
            scales.append(
                DashboardDatasetScale(
                    dataset=dataset.value,
                    table_count=total,
                    nonempty_count=nonempty,
                    empty_count=empty,
                    last_snapshot_at=snap,
                    last_synced_at=synced,
                )
            )
        return scales
