"""排程管理(ScheduleService)與執行紀錄 / 手動觸發(RunService)。

兩個 service 同檔:task-005 affected_files 白名單僅含本檔,run 查詢 / 手動觸發
與排程同屬一個功能面(排程 → 執行 → 紀錄),不另拆檔。
"""

import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import AsyncTaskiqTask, InMemoryBroker

from app.core.exceptions import AppError
from app.models import EtlRun, EtlRunLog, Schedule
from app.repositories.run_repo import RunRepository
from app.repositories.schedule_repo import ScheduleRepository
from app.schemas.run import (
    RunListResponse,
    RunLogListResponse,
    RunLogResponse,
    RunLogStatus,
    RunStatus,
    RunSummaryResponse,
    RunTriggerRequest,
    RunTriggerResponse,
    TriggerType,
)
from app.schemas.schedule import (
    ScheduleCreateRequest,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdateRequest,
)
from app.services.audit_service import AuditService
from app.worker.broker import broker
from app.worker.tasks import run_etl

# cron 5 欄位(分 時 日 月 週),每欄僅允許數字與 * / , - ;語意由 taskiq scheduler 解讀
_CRON_FIELD_RE = re.compile(r"^[\d*/,-]+$")
_CRON_FIELD_COUNT = 5


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

    # ── 查詢 ────────────────────────────────────────────────────────────
    async def list_schedules(self, *, page: int, page_size: int) -> ScheduleListResponse:
        offset = (page - 1) * page_size
        schedules, total = await self._repo.list_schedules(offset=offset, limit=page_size)
        table_pids = [s.etl_table_pid for s in schedules if s.etl_table_pid is not None]
        uid_map = await self._repo.etl_table_uid_by_pid(table_pids)
        items = [self._to_response(s, uid_map) for s in schedules]
        return ScheduleListResponse(items=items, total=total, page=page, page_size=page_size)

    async def get_schedule(self, uid: UUID) -> ScheduleResponse:
        schedule = await self._get_or_404(uid)
        return await self._to_response_single(schedule)

    # ── 寫入 ────────────────────────────────────────────────────────────
    async def create_schedule(
        self, payload: ScheduleCreateRequest, actor_uid: UUID
    ) -> ScheduleResponse:
        cron_expr = _validate_cron_expr(payload.cron_expr)
        if await self._repo.find_by_name(payload.name) is not None:
            raise AppError("排程名稱已存在", response_code=409, status_code=409)
        etl_table_pid = await self._resolve_etl_table_pid(payload.etl_table_uid)
        schedule = await self._repo.create(
            name=payload.name,
            cron_expr=cron_expr,
            is_enabled=payload.is_enabled,
            etl_table_pid=etl_table_pid,
            description=payload.description,
            actor_uid=actor_uid,
        )
        await self._audit.log(
            action="schedule_create",
            actor_uid=actor_uid,
            target_type="schedule",
            target_uid=schedule.uid,
            detail=f"新增排程 {schedule.name}(cron={schedule.cron_expr})",
        )
        return await self._to_response_single(schedule)

    async def update_schedule(
        self, uid: UUID, payload: ScheduleUpdateRequest, actor_uid: UUID
    ) -> ScheduleResponse:
        schedule = await self._get_or_404(uid)
        fields_set = payload.model_fields_set
        if "name" in fields_set and payload.name is not None:
            existing = await self._repo.find_by_name(payload.name)
            if existing is not None and existing.pid != schedule.pid:
                raise AppError("排程名稱已存在", response_code=409, status_code=409)
            schedule.name = payload.name
        if "cron_expr" in fields_set and payload.cron_expr is not None:
            schedule.cron_expr = _validate_cron_expr(payload.cron_expr)
        if "etl_table_uid" in fields_set:
            schedule.etl_table_pid = await self._resolve_etl_table_pid(payload.etl_table_uid)
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

    async def delete_schedule(self, uid: UUID, actor_uid: UUID) -> None:
        schedule = await self._get_or_404(uid)
        await self._repo.soft_delete(schedule, actor_uid)
        await self._audit.log(
            action="schedule_delete",
            actor_uid=actor_uid,
            target_type="schedule",
            target_uid=schedule.uid,
            detail=f"刪除(軟刪除)排程 {schedule.name}",
        )

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

    # ── 內部 ────────────────────────────────────────────────────────────
    async def _get_or_404(self, uid: UUID) -> Schedule:
        schedule = await self._repo.find_by_uid(uid)
        if schedule is None:
            raise AppError("排程不存在", response_code=404, status_code=404)
        return schedule

    async def _resolve_etl_table_pid(self, etl_table_uid: UUID | None) -> int | None:
        if etl_table_uid is None:
            return None
        table = await self._repo.find_etl_table_by_uid(etl_table_uid)
        if table is None:
            raise AppError("指定的 ETL 表設定不存在", response_code=400, status_code=400)
        return table.pid

    async def _to_response_single(self, schedule: Schedule) -> ScheduleResponse:
        pids = [schedule.etl_table_pid] if schedule.etl_table_pid is not None else []
        uid_map = await self._repo.etl_table_uid_by_pid(pids)
        return self._to_response(schedule, uid_map)

    def _to_response(self, schedule: Schedule, uid_map: dict[int, UUID]) -> ScheduleResponse:
        return ScheduleResponse(
            uid=schedule.uid,
            name=schedule.name,
            cron_expr=schedule.cron_expr,
            is_enabled=schedule.is_enabled,
            etl_table_uid=(
                uid_map.get(schedule.etl_table_pid)
                if schedule.etl_table_pid is not None
                else None
            ),
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

    # ── 手動觸發(enqueue 至 taskiq;task 定義屬 task-007)────────────────
    async def trigger_manual(
        self, payload: RunTriggerRequest, actor_uid: UUID | None = None
    ) -> RunTriggerResponse:
        """手動觸發一次 ETL。

        actor_uid 預設 None 維持既有呼叫端(api/v1/runs.py)相容;
        呼叫端補傳 `actor_uid=user.uid` 後,稽核 run_trigger 即帶操作者。
        """
        etl_table_pid: int | None = None
        if payload.etl_table_uid is not None:
            table = await self._ref_repo.find_etl_table_by_uid(payload.etl_table_uid)
            if table is None:
                raise AppError("指定的 ETL 表設定不存在", response_code=400, status_code=400)
            etl_table_pid = table.pid
        task = await run_etl.kiq(trigger_type="manual", etl_table_pid=etl_table_pid)
        run_uid = await self._resolve_run_uid(task)
        await self._audit.log(
            action="run_trigger",
            actor_uid=actor_uid,
            target_type="etl_run",
            target_uid=run_uid,
            detail=(
                f"手動觸發 ETL(task_id={task.task_id}"
                + (
                    f",指定表 uid={payload.etl_table_uid}"
                    if payload.etl_table_uid is not None
                    else ",全部啟用表"
                )
                + ")"
            ),
        )
        return RunTriggerResponse(task_id=task.task_id, run_uid=run_uid)

    async def _resolve_run_uid(
        self, task: AsyncTaskiqTask[dict[str, object]]
    ) -> UUID | None:
        """就地執行 broker(InMemoryBroker)已跑完 → 以結果 run_pid 換 uid;佇列模式回 None。"""
        if not isinstance(broker, InMemoryBroker):
            return None
        result = await task.wait_result(timeout=5)
        if result.is_err:
            return None
        return_value: object = result.return_value
        if not isinstance(return_value, dict):
            return None
        run_pid = return_value.get("run_pid")
        if not isinstance(run_pid, int):
            return None
        run = await self._repo.find_by_pid(run_pid)
        return run.uid if run is not None else None

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
