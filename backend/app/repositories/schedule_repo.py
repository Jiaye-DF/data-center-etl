from collections.abc import Sequence
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EtlRun, EtlTable, Schedule
from app.utils.datetime import db_now as _db_now


class ScheduleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── schedules ───────────────────────────────────────────────────────
    async def list_schedules(
        self, *, offset: int, limit: int
    ) -> tuple[list[Schedule], int]:
        total = (
            await self._db.execute(
                select(func.count())
                .select_from(Schedule)
                .where(Schedule.is_deleted.is_(False))
            )
        ).scalar_one()
        rows = (
            await self._db.execute(
                select(Schedule)
                .where(Schedule.is_deleted.is_(False))
                .order_by(Schedule.pid)
                .offset(offset)
                .limit(limit)
            )
        ).scalars()
        return list(rows.all()), total

    async def find_by_uid(self, uid: UUID) -> Schedule | None:
        stmt = select(Schedule).where(Schedule.uid == uid, Schedule.is_deleted.is_(False))
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def find_by_name(self, name: str) -> Schedule | None:
        stmt = select(Schedule).where(Schedule.name == name, Schedule.is_deleted.is_(False))
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def create(
        self,
        *,
        name: str,
        cron_expr: str,
        is_enabled: bool,
        description: str | None,
        actor_uid: UUID,
    ) -> Schedule:
        # v1.3:同步只有「增量同步全部表」單一語意,不再逐表選擇,etl_table_pid 恆為 NULL
        schedule = Schedule(
            uid=uuid4(),
            name=name,
            cron_expr=cron_expr,
            is_enabled=is_enabled,
            etl_table_pid=None,
            description=description,
            created_by=actor_uid,
            updated_by=actor_uid,
        )
        self._db.add(schedule)
        await self._db.flush()
        return schedule

    async def touch(self, schedule: Schedule, actor_uid: UUID) -> None:
        """更新審計欄位(欄位值變更由呼叫端先行設定)。"""
        schedule.updated_by = actor_uid
        schedule.updated_at = _db_now()
        await self._db.flush()

    async def soft_delete(self, schedule: Schedule, actor_uid: UUID) -> None:
        schedule.is_deleted = True
        await self.touch(schedule, actor_uid)

    # ── 關聯查詢(etl_tables / schedules 參照解析)──────────────────────
    async def find_etl_table_by_uid(self, uid: UUID) -> EtlTable | None:
        stmt = select(EtlTable).where(EtlTable.uid == uid, EtlTable.is_deleted.is_(False))
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def etl_table_uid_by_pid(self, pids: Sequence[int]) -> dict[int, UUID]:
        """pid → uid 對照(對外 API 禁曝內部主鍵;含已軟刪表,歷史參照仍可解析)。"""
        if not pids:
            return {}
        stmt = select(EtlTable.pid, EtlTable.uid).where(EtlTable.pid.in_(pids))
        rows = (await self._db.execute(stmt)).all()
        return {int(pid): uid for pid, uid in rows}

    async def schedule_ref_by_pid(self, pids: Sequence[int]) -> dict[int, tuple[UUID, str]]:
        """pid →(uid, name)對照(run 清單顯示來源排程;含已軟刪排程)。"""
        if not pids:
            return {}
        stmt = select(Schedule.pid, Schedule.uid, Schedule.name).where(Schedule.pid.in_(pids))
        rows = (await self._db.execute(stmt)).all()
        return {int(pid): (uid, str(name)) for pid, uid, name in rows}

    async def last_run_by_schedule_pid(
        self, pids: Sequence[int]
    ) -> dict[int, tuple[str, datetime | None]]:
        """schedule_pid →(最新 run 的 status, finished_at)對照(排程清單顯示上次執行結果)。

        每個 schedule_pid 取「最新一筆未刪除 etl_runs」(以 pid 遞減判定最新)。
        """
        if not pids:
            return {}
        stmt = (
            select(EtlRun.schedule_pid, EtlRun.status, EtlRun.finished_at)
            .where(EtlRun.schedule_pid.in_(pids), EtlRun.is_deleted.is_(False))
            .distinct(EtlRun.schedule_pid)
            .order_by(EtlRun.schedule_pid, EtlRun.pid.desc())
        )
        rows = (await self._db.execute(stmt)).all()
        return {
            int(schedule_pid): (str(status), finished_at)
            for schedule_pid, status, finished_at in rows
        }
