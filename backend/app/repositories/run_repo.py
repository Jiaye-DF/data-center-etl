from uuid import UUID

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EtlRun, EtlRunLog


class RunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── dashboard 聚合(最新 run / 近 N 筆統計)──────────────────────────
    async def latest_run(self) -> EtlRun | None:
        """最新一筆未刪除 run(pid 遞增即時間序)。"""
        stmt = (
            select(EtlRun)
            .where(EtlRun.is_deleted.is_(False))
            .order_by(EtlRun.pid.desc())
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def recent_run_stats(self, limit: int) -> tuple[int, int, int]:
        """最近 limit 筆 run 的 (總數, 成功數, 失敗數)。"""
        recent = (
            select(EtlRun.status)
            .where(EtlRun.is_deleted.is_(False))
            .order_by(EtlRun.pid.desc())
            .limit(limit)
            .subquery()
        )
        stmt = select(
            func.count(),
            func.count(case((recent.c.status == "success", 1))),
            func.count(case((recent.c.status == "failed", 1))),
        )
        total, success, failed = (await self._db.execute(stmt)).one()
        return int(total), int(success), int(failed)

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

    async def latest_running_run(self) -> EtlRun | None:
        """最新一筆執行中(status='running')且未刪除的 run(供 /runs/active 進度輪詢)。"""
        stmt = (
            select(EtlRun)
            .where(EtlRun.status == "running", EtlRun.is_deleted.is_(False))
            .order_by(EtlRun.pid.desc())
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def log_status_counts(self, run_pid: int) -> dict[str, int]:
        """該 run 逐表 log 依狀態聚合筆數(一次 GROUP BY;分子不加新寫入,純讀端聚合)。"""
        stmt = (
            select(EtlRunLog.status, func.count())
            .where(EtlRunLog.etl_run_pid == run_pid, EtlRunLog.is_deleted.is_(False))
            .group_by(EtlRunLog.status)
        )
        rows = (await self._db.execute(stmt)).all()
        return {status: int(count) for status, count in rows}

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
