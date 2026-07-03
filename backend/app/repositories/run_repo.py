from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EtlRun, EtlRunLog


class RunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── etl_runs ────────────────────────────────────────────────────────
    async def list_runs(
        self,
        *,
        offset: int,
        limit: int,
        status: str | None,
        trigger_type: str | None,
    ) -> tuple[list[EtlRun], int]:
        def _filtered(stmt: Select[tuple[EtlRun]]) -> Select[tuple[EtlRun]]:
            stmt = stmt.where(EtlRun.is_deleted.is_(False))
            if status is not None:
                stmt = stmt.where(EtlRun.status == status)
            if trigger_type is not None:
                stmt = stmt.where(EtlRun.trigger_type == trigger_type)
            return stmt

        count_stmt = _filtered(select(EtlRun)).with_only_columns(func.count())
        total = (await self._db.execute(count_stmt)).scalar_one()
        rows = (
            await self._db.execute(
                # 最新在前(pid 遞增即時間序;主鍵索引可走)
                _filtered(select(EtlRun)).order_by(EtlRun.pid.desc()).offset(offset).limit(limit)
            )
        ).scalars()
        return list(rows.all()), total

    async def find_by_uid(self, uid: UUID) -> EtlRun | None:
        stmt = select(EtlRun).where(EtlRun.uid == uid, EtlRun.is_deleted.is_(False))
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def find_by_pid(self, pid: int) -> EtlRun | None:
        stmt = select(EtlRun).where(EtlRun.pid == pid, EtlRun.is_deleted.is_(False))
        return (await self._db.execute(stmt)).scalar_one_or_none()

    # ── etl_run_logs(單 run 逐表明細)──────────────────────────────────
    async def list_logs(
        self,
        *,
        etl_run_pid: int,
        offset: int,
        limit: int,
        status: str | None,
    ) -> tuple[list[EtlRunLog], int]:
        def _filtered(stmt: Select[tuple[EtlRunLog]]) -> Select[tuple[EtlRunLog]]:
            stmt = stmt.where(
                EtlRunLog.etl_run_pid == etl_run_pid,
                EtlRunLog.is_deleted.is_(False),
            )
            if status is not None:
                stmt = stmt.where(EtlRunLog.status == status)
            return stmt

        count_stmt = _filtered(select(EtlRunLog)).with_only_columns(func.count())
        total = (await self._db.execute(count_stmt)).scalar_one()
        rows = (
            await self._db.execute(
                _filtered(select(EtlRunLog)).order_by(EtlRunLog.pid).offset(offset).limit(limit)
            )
        ).scalars()
        return list(rows.all()), total
