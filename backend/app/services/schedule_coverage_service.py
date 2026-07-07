"""依表檢視 coverage service:組 schema 概覽 / 來源表涵蓋清單,與逐表排除切換。

coverage 語意:mirror_sync 為「全表增量」,所有啟用排程一律適用於所有來源表。故
- 每張表「納入」= 未被排除(sync_excluded=false)且系統至少有一個啟用排程。
- 系統無任何啟用排程時,所有表皆未涵蓋(included=false)。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.repositories.schedule_coverage_repo import (
    CoverageRow,
    ScheduleCoverageRepository,
)
from app.schemas.schedule_coverage import (
    CoverageListResponse,
    CoverageScheduleInfo,
    CoverageSchemaListResponse,
    SchemaCoverageSummary,
    TableCoverageItem,
)


class ScheduleCoverageService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = ScheduleCoverageRepository(db)

    async def list_schemas(self) -> CoverageSchemaListResponse:
        schedules = await self._repo.enabled_schedules()
        summaries = await self._repo.list_schema_summaries()
        return CoverageSchemaListResponse(
            items=[
                SchemaCoverageSummary(
                    schema_name=schema, table_count=count, excluded_count=excluded
                )
                for schema, count, excluded in summaries
            ],
            has_enabled_schedule=len(schedules) > 0,
            schedules=self._to_schedule_infos(schedules),
        )

    async def list_tables(
        self,
        schema: str,
        *,
        page: int,
        page_size: int,
        inclusion: str,
        last_result: str,
        keyword: str,
    ) -> CoverageListResponse:
        schedules = await self._repo.enabled_schedules()
        has_enabled = len(schedules) > 0
        offset = (page - 1) * page_size
        rows, total = await self._repo.list_tables(
            schema,
            offset=offset,
            limit=page_size,
            inclusion=inclusion,
            last_result=last_result,
            keyword=keyword,
        )
        return CoverageListResponse(
            items=[self._to_item(row, has_enabled) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
            schedules=self._to_schedule_infos(schedules),
            has_enabled_schedule=has_enabled,
        )

    async def set_exclusion(
        self, uid: UUID, *, excluded: bool, actor_uid: UUID
    ) -> TableCoverageItem:
        row = await self._repo.find_meta_by_uid(uid)
        if row is None:
            raise AppError("資料表快照不存在", response_code=404, status_code=404)
        await self._repo.set_excluded(row, excluded, actor_uid)
        schedules = await self._repo.enabled_schedules()
        has_enabled = len(schedules) > 0
        last_status = await self._repo.latest_log_status(
            row.schema_name, row.table_name
        )
        return TableCoverageItem(
            uid=row.uid,
            schema_name=row.schema_name,
            table_name=row.table_name,
            business_name=row.business_name,
            sync_excluded=row.sync_excluded,
            included=(not row.sync_excluded) and has_enabled,
            last_synced_at=row.last_synced_at,
            last_run_status=last_status,
            row_count=row.row_count,
        )

    # ── 內部 ────────────────────────────────────────────────────────────
    @staticmethod
    def _to_schedule_infos(
        schedules: list[tuple[str, str]],
    ) -> list[CoverageScheduleInfo]:
        return [
            CoverageScheduleInfo(name=name, cron_expr=cron_expr)
            for name, cron_expr in schedules
        ]

    @staticmethod
    def _to_item(row: CoverageRow, has_enabled: bool) -> TableCoverageItem:
        return TableCoverageItem(
            uid=row.uid,
            schema_name=row.schema_name,
            table_name=row.table_name,
            business_name=row.business_name,
            sync_excluded=row.sync_excluded,
            included=(not row.sync_excluded) and has_enabled,
            last_synced_at=row.last_synced_at,
            last_run_status=row.last_status,
            row_count=row.row_count,
        )
