from collections.abc import Sequence
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EtlMapping, EtlRunLog, EtlTable
from app.utils.datetime import db_now as _db_now


class EtlConfigRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── etl_tables ──────────────────────────────────────────────────────
    async def list_tables(self, *, offset: int, limit: int) -> tuple[list[EtlTable], int]:
        total = (
            await self._db.execute(
                select(func.count())
                .select_from(EtlTable)
                .where(EtlTable.is_deleted.is_(False))
            )
        ).scalar_one()
        rows = (
            await self._db.execute(
                select(EtlTable)
                .where(EtlTable.is_deleted.is_(False))
                .order_by(EtlTable.pid)
                .offset(offset)
                .limit(limit)
            )
        ).scalars()
        return list(rows.all()), total

    async def find_table_by_uid(self, uid: UUID) -> EtlTable | None:
        stmt = select(EtlTable).where(EtlTable.uid == uid, EtlTable.is_deleted.is_(False))
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def find_table_by_source(
        self, source_schema: str, source_table: str
    ) -> EtlTable | None:
        stmt = select(EtlTable).where(
            EtlTable.source_schema == source_schema,
            EtlTable.source_table == source_table,
            EtlTable.is_deleted.is_(False),
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def create_table(
        self,
        *,
        source_schema: str,
        source_table: str,
        target_schema: str,
        target_table: str,
        description: str | None,
        is_enabled: bool,
        actor_uid: UUID,
    ) -> EtlTable:
        table = EtlTable(
            uid=uuid4(),
            source_schema=source_schema,
            source_table=source_table,
            target_schema=target_schema,
            target_table=target_table,
            description=description,
            is_enabled=is_enabled,
            created_by=actor_uid,
            updated_by=actor_uid,
        )
        self._db.add(table)
        await self._db.flush()
        return table

    async def touch_table(self, table: EtlTable, actor_uid: UUID) -> None:
        """更新審計欄位(欄位值變更由呼叫端先行設定)。"""
        table.updated_by = actor_uid
        table.updated_at = _db_now()
        await self._db.flush()

    async def soft_delete_table(self, table: EtlTable, actor_uid: UUID) -> None:
        table.is_deleted = True
        await self.touch_table(table, actor_uid)

    # ── etl_mappings ────────────────────────────────────────────────────
    async def list_mappings_by_table_pid(self, etl_table_pid: int) -> list[EtlMapping]:
        stmt = (
            select(EtlMapping)
            .where(
                EtlMapping.etl_table_pid == etl_table_pid,
                EtlMapping.is_deleted.is_(False),
            )
            .order_by(EtlMapping.sort_order, EtlMapping.pid)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def mapping_count_by_table_pid(self, pids: Sequence[int]) -> dict[int, int]:
        if not pids:
            return {}
        stmt = (
            select(EtlMapping.etl_table_pid, func.count())
            .where(
                EtlMapping.etl_table_pid.in_(pids),
                EtlMapping.is_deleted.is_(False),
            )
            .group_by(EtlMapping.etl_table_pid)
        )
        rows = (await self._db.execute(stmt)).all()
        return {int(pid): int(count) for pid, count in rows}

    async def create_mapping(
        self,
        *,
        etl_table_pid: int,
        source_column: str,
        target_column: str,
        transform_type: str | None,
        comment: str,
        sort_order: int,
        actor_uid: UUID,
    ) -> EtlMapping:
        mapping = EtlMapping(
            uid=uuid4(),
            etl_table_pid=etl_table_pid,
            source_column=source_column,
            target_column=target_column,
            transform_type=transform_type,
            comment=comment,
            sort_order=sort_order,
            created_by=actor_uid,
            updated_by=actor_uid,
        )
        self._db.add(mapping)
        await self._db.flush()
        return mapping

    async def soft_delete_mappings_by_table_pid(
        self, etl_table_pid: int, actor_uid: UUID
    ) -> None:
        stmt = (
            update(EtlMapping)
            .where(
                EtlMapping.etl_table_pid == etl_table_pid,
                EtlMapping.is_deleted.is_(False),
            )
            .values(is_deleted=True, updated_by=actor_uid, updated_at=_db_now())
        )
        await self._db.execute(stmt)
        await self._db.flush()

    # ── etl_run_logs(最近執行狀態)─────────────────────────────────────
    async def latest_run_log_by_table_pid(self, pids: Sequence[int]) -> dict[int, EtlRunLog]:
        if not pids:
            return {}
        stmt = (
            select(EtlRunLog)
            .where(
                EtlRunLog.etl_table_pid.in_(pids),
                EtlRunLog.is_deleted.is_(False),
            )
            .order_by(EtlRunLog.etl_table_pid, EtlRunLog.pid.desc())
            .distinct(EtlRunLog.etl_table_pid)
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        result: dict[int, EtlRunLog] = {}
        for log in rows:
            if log.etl_table_pid is not None:
                result[log.etl_table_pid] = log
        return result
