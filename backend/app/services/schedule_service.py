"""排程管理(ScheduleService)與執行紀錄查詢(RunService)。

兩個 service 同檔:run 查詢與排程同屬一個功能面(排程 → 執行 → 紀錄),不另拆檔。
v1.3.1:排程由「條目 CRUD」重構為「逐表視角 + 生命週期跟隨快照」,
config-ETL 手動觸發已隨 task-005 移除。
"""

import re
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models import EtlRun, EtlRunLog, Schedule
from app.repositories.run_repo import RunRepository
from app.repositories.schedule_repo import ScheduleRepository
from app.schemas.run import (
    ActiveRunResponse,
    RunListResponse,
    RunLogListResponse,
    RunLogResponse,
    RunLogStatus,
    RunStatus,
    RunSummaryResponse,
    TriggerType,
)
from app.schemas.schedule import (
    ScheduleBatchEnabledResponse,
    ScheduleResponse,
    ScheduleSchemaSummary,
    ScheduleSchemaSummaryListResponse,
    ScheduleTableViewItem,
    ScheduleTableViewListResponse,
    ScheduleUpdateRequest,
)
from app.services.audit_service import AuditService

# cron 5 欄位(分 時 日 月 週),每欄僅允許數字與 * / , - ;語意由 taskiq scheduler 解讀
_CRON_FIELD_RE = re.compile(r"^[\d*/,-]+$")
_CRON_FIELD_COUNT = 5

# 排程時段篩選輸入(HH:MM,24 小時制)
_TIME_OF_DAY_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]?\d)$")


def _parse_time_of_day(value: str | None) -> int | None:
    """把 'HH:MM' 轉 minute-of-day(0–1439);空字串 / None 回 None;格式錯誤丟 400。"""
    if value is None or value.strip() == "":
        return None
    match = _TIME_OF_DAY_RE.match(value.strip())
    if match is None:
        raise AppError(
            "時段格式不合法(須為 HH:MM,24 小時制)",
            response_code=400,
            status_code=400,
        )
    return int(match.group(1)) * 60 + int(match.group(2))

# v1.3:同步只有單一語意「增量同步全部來源表」,排程不再逐表選擇
_JOB_DESC = "增量同步全部表"


def _validate_cron_expr(cron_expr: str) -> str:
    fields = cron_expr.split()
    if len(fields) != _CRON_FIELD_COUNT or not all(_CRON_FIELD_RE.match(f) for f in fields):
        raise AppError(
            "cron_expr 格式不合法(須為 5 欄位:分 時 日 月 週)",
            response_code=400,
            status_code=400,
        )
    return " ".join(fields)


class ScheduleService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = ScheduleRepository(db)
        self._audit = AuditService(db)

    # ── 查詢(逐表視角)──────────────────────────────────────────────────
    async def list_tables_view(
        self,
        *,
        schema: str,
        page: int,
        page_size: int,
        enabled: str,
        last_result: str,
        keyword: str,
        keyword_exact: bool = False,
        rows_filter: str = "all",
        time_from: str | None = None,
        time_to: str | None = None,
    ) -> ScheduleTableViewListResponse:
        offset = (page - 1) * page_size
        rows, total = await self._repo.list_tables_view(
            schema=schema,
            offset=offset,
            limit=page_size,
            enabled=enabled,
            last_result=last_result,
            keyword=keyword,
            exact=keyword_exact,
            rows=rows_filter,
            time_from=_parse_time_of_day(time_from),
            time_to=_parse_time_of_day(time_to),
        )
        items = [
            ScheduleTableViewItem(
                table_name=row.table_name,
                business_name=row.business_name,
                schedule_uid=row.schedule_uid,
                cron_expr=row.cron_expr,
                is_enabled=row.is_enabled,
                description=row.description,
                last_synced_at=row.last_synced_at,
                last_run_status=row.last_run_status,
            )
            for row in rows
        ]
        return ScheduleTableViewListResponse(
            items=items, total=total, page=page, page_size=page_size
        )

    async def list_schema_summaries(self) -> ScheduleSchemaSummaryListResponse:
        summaries = await self._repo.list_schema_summaries()
        items = [
            ScheduleSchemaSummary(
                schema_name=schema_name, table_count=table_count, enabled_count=enabled_count
            )
            for schema_name, table_count, enabled_count in summaries
        ]
        return ScheduleSchemaSummaryListResponse(items=items)

    # ── 寫入(僅 cron / 啟停 / 描述;禁改綁定表)────────────────────────
    async def update_schedule(
        self, uid: UUID, payload: ScheduleUpdateRequest, actor_uid: UUID
    ) -> ScheduleResponse:
        schedule = await self._get_or_404(uid)
        fields_set = payload.model_fields_set
        if "cron_expr" in fields_set and payload.cron_expr is not None:
            schedule.cron_expr = _validate_cron_expr(payload.cron_expr)
        if "is_enabled" in fields_set and payload.is_enabled is not None:
            schedule.is_enabled = payload.is_enabled
        if "description" in fields_set:
            schedule.description = payload.description
        await self._repo.touch(schedule, actor_uid)
        await self._audit.log(
            action="schedule_update",
            actor_uid=actor_uid,
            target_type="schedule",
            target_uid=schedule.uid,
            detail=(
                f"更新排程 {schedule.name}"
                f"(欄位:{', '.join(sorted(fields_set)) or '無'})"
            ),
        )
        return await self._to_response_single(schedule)

    async def set_enabled(
        self, uid: UUID, *, enabled: bool, actor_uid: UUID
    ) -> ScheduleResponse:
        schedule = await self._get_or_404(uid)
        schedule.is_enabled = enabled
        await self._repo.touch(schedule, actor_uid)
        await self._audit.log(
            action="schedule_enable" if enabled else "schedule_disable",
            actor_uid=actor_uid,
            target_type="schedule",
            target_uid=schedule.uid,
            detail=f"{'啟用' if enabled else '停用'}排程 {schedule.name}",
        )
        return await self._to_response_single(schedule)

    async def batch_set_enabled(
        self,
        *,
        schema: str | None,
        enabled: bool,
        actor_uid: UUID,
        filter_enabled: str = "all",
        filter_last_result: str = "all",
        filter_keyword: str = "",
        filter_keyword_exact: bool = False,
        filter_rows: str = "all",
        filter_time_from: str | None = None,
        filter_time_to: str | None = None,
    ) -> ScheduleBatchEnabledResponse:
        """對「符合篩選(schema + 啟用狀態 + 上次結果 + 關鍵字 + 筆數 + 時段)」的來源表排程批次啟停。

        篩選皆為 all / 空 時等同「全部來源表排程」;帶篩選時僅作用於逐表列表命中的表。
        """
        affected = await self._repo.batch_set_enabled(
            schema=schema,
            enabled=enabled,
            only_source_tables=True,
            actor_uid=actor_uid,
            filter_enabled=filter_enabled,
            filter_last_result=filter_last_result,
            filter_keyword=filter_keyword,
            filter_keyword_exact=filter_keyword_exact,
            filter_rows=filter_rows,
            filter_time_from=_parse_time_of_day(filter_time_from),
            filter_time_to=_parse_time_of_day(filter_time_to),
        )
        has_filter = (
            filter_enabled != "all"
            or filter_last_result != "all"
            or filter_keyword.strip() != ""
            or filter_rows != "all"
            or filter_time_from is not None
            or filter_time_to is not None
        )
        await self._audit.log(
            action="schedule_batch_enable" if enabled else "schedule_batch_disable",
            actor_uid=actor_uid,
            target_type="schedule",
            detail=(
                f"批次{'啟用' if enabled else '停用'}排程"
                f"(schema={schema or '全部'}"
                f"{',符合篩選' if has_filter else ''},影響 {affected} 筆)"
            ),
        )
        return ScheduleBatchEnabledResponse(affected=affected)

    # ── 內部 ────────────────────────────────────────────────────────────
    async def _get_or_404(self, uid: UUID) -> Schedule:
        schedule = await self._repo.find_by_uid(uid)
        if schedule is None:
            raise AppError("排程不存在", response_code=404, status_code=404)
        return schedule

    async def _to_response_single(self, schedule: Schedule) -> ScheduleResponse:
        last_run_map = await self._repo.last_run_by_schedule_pid([schedule.pid])
        return self._to_response(schedule, last_run_map)

    def _to_response(
        self,
        schedule: Schedule,
        last_run_map: dict[int, tuple[str, datetime | None]],
    ) -> ScheduleResponse:
        last_run = last_run_map.get(schedule.pid)
        return ScheduleResponse(
            uid=schedule.uid,
            name=schedule.name,
            cron_expr=schedule.cron_expr,
            is_enabled=schedule.is_enabled,
            job_desc=_JOB_DESC,
            last_run_status=last_run[0] if last_run is not None else None,
            last_run_finished_at=last_run[1] if last_run is not None else None,
            description=schedule.description,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )


class RunService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = RunRepository(db)
        self._ref_repo = ScheduleRepository(db)
        self._audit = AuditService(db)

    # ── 查詢 ────────────────────────────────────────────────────────────
    async def list_runs(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None,
        trigger_type: str | None,
    ) -> RunListResponse:
        offset = (page - 1) * page_size
        runs, total = await self._repo.list_runs(
            offset=offset, limit=page_size, status=status, trigger_type=trigger_type
        )
        schedule_pids = [r.schedule_pid for r in runs if r.schedule_pid is not None]
        ref_map = await self._ref_repo.schedule_ref_by_pid(schedule_pids)
        items = [self._to_summary(r, ref_map) for r in runs]
        return RunListResponse(items=items, total=total, page=page, page_size=page_size)

    async def get_run(self, uid: UUID) -> RunSummaryResponse:
        run = await self._get_or_404(uid)
        pids = [run.schedule_pid] if run.schedule_pid is not None else []
        ref_map = await self._ref_repo.schedule_ref_by_pid(pids)
        return self._to_summary(run, ref_map)

    async def get_active_run(self) -> ActiveRunResponse | None:
        """最新一筆執行中 run 的進度快照;無執行中 run 回 None(供 /runs/active 輪詢)。"""
        run = await self._repo.latest_running_run()
        if run is None:
            return None
        counts = await self._repo.log_status_counts(run.pid)
        success_tables = counts.get("success", 0)
        failed_tables = counts.get("failed", 0)
        skipped_tables = counts.get("skipped", 0)
        running_tables = counts.get("running", 0)
        return ActiveRunResponse(
            uid=run.uid,
            trigger_type=TriggerType(run.trigger_type),
            started_at=run.started_at,
            total_tables=run.total_tables,
            success_tables=success_tables,
            failed_tables=failed_tables,
            skipped_tables=skipped_tables,
            running_tables=running_tables,
            processed_tables=success_tables + failed_tables + skipped_tables,
        )

    async def list_run_logs(
        self,
        uid: UUID,
        *,
        page: int,
        page_size: int,
        status: str | None,
    ) -> RunLogListResponse:
        run = await self._get_or_404(uid)
        offset = (page - 1) * page_size
        logs, total = await self._repo.list_logs(
            etl_run_pid=run.pid, offset=offset, limit=page_size, status=status
        )
        table_pids = [log.etl_table_pid for log in logs if log.etl_table_pid is not None]
        uid_map = await self._ref_repo.etl_table_uid_by_pid(table_pids)
        items = [self._to_log_response(log, uid_map) for log in logs]
        return RunLogListResponse(items=items, total=total, page=page, page_size=page_size)

    # ── 內部 ────────────────────────────────────────────────────────────
    async def _get_or_404(self, uid: UUID) -> EtlRun:
        run = await self._repo.find_by_uid(uid)
        if run is None:
            raise AppError("執行紀錄不存在", response_code=404, status_code=404)
        return run

    def _to_summary(
        self, run: EtlRun, ref_map: dict[int, tuple[UUID, str]]
    ) -> RunSummaryResponse:
        ref = ref_map.get(run.schedule_pid) if run.schedule_pid is not None else None
        return RunSummaryResponse(
            uid=run.uid,
            trigger_type=TriggerType(run.trigger_type),
            status=RunStatus(run.status),
            schedule_uid=ref[0] if ref is not None else None,
            schedule_name=ref[1] if ref is not None else None,
            started_at=run.started_at,
            finished_at=run.finished_at,
            total_tables=run.total_tables,
            success_tables=run.success_tables,
            failed_tables=run.failed_tables,
            error_message=run.error_message,
            created_at=run.created_at,
        )

    def _to_log_response(
        self, log: EtlRunLog, uid_map: dict[int, UUID]
    ) -> RunLogResponse:
        return RunLogResponse(
            uid=log.uid,
            etl_table_uid=(
                uid_map.get(log.etl_table_pid) if log.etl_table_pid is not None else None
            ),
            source_schema=log.source_schema,
            source_table=log.source_table,
            status=RunLogStatus(log.status),
            row_count=log.row_count,
            duration_ms=log.duration_ms,
            started_at=log.started_at,
            finished_at=log.finished_at,
            error_message=log.error_message,
            error_stack=log.error_stack,
        )
