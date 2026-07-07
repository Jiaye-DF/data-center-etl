"""依表檢視 coverage repo:啟用排程清單、schema 概況、來源表涵蓋分頁查詢與逐表排除寫入。

- 讀取一律過濾 is_deleted(軟刪除規範 `04-databases/02-soft-delete.md`)。
- 「上次執行結果」以 etl_run_logs 對 (source_schema, source_table) 取最新一筆 status
  (DISTINCT ON,依 pid DESC),LEFT JOIN 進主查詢。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, Row, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.etl_run_log import EtlRunLog
from app.models.rds_table_meta import Dataset, RdsTableMeta
from app.models.schedule import Schedule
from app.utils.datetime import db_now as _db_now

# 主查詢每列欄位順序:uid, schema, table, business_name, sync_excluded,
# last_synced_at, row_count, last_run_status
CoverageRow = Row[
    tuple[UUID, str, str, str | None, bool, datetime | None, int, str | None]
]


class ScheduleCoverageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def enabled_schedules(self) -> list[tuple[str, str]]:
        """回目前啟用且未刪除的排程 (name, cron_expr),依 pid 排序。"""
        stmt = (
            select(Schedule.name, Schedule.cron_expr)
            .where(
                Schedule.is_enabled.is_(True),
                Schedule.is_deleted.is_(False),
            )
            .order_by(Schedule.pid)
        )
        rows = (await self._db.execute(stmt)).all()
        return [(str(name), str(cron_expr)) for name, cron_expr in rows]

    async def list_schema_summaries(self) -> list[tuple[str, int, int]]:
        """聚合來源表各 schema 的 (表數, 被排除數),未刪除範圍,依 schema 名排序。"""
        stmt = (
            select(
                RdsTableMeta.schema_name,
                func.count(),
                func.count().filter(RdsTableMeta.sync_excluded.is_(True)),
            )
            .where(
                RdsTableMeta.dataset == Dataset.SOURCE,
                RdsTableMeta.is_deleted.is_(False),
            )
            .group_by(RdsTableMeta.schema_name)
            .order_by(RdsTableMeta.schema_name)
        )
        rows = (await self._db.execute(stmt)).all()
        return [
            (str(schema), int(count), int(excluded))
            for schema, count, excluded in rows
        ]

    async def list_tables(
        self,
        schema: str,
        *,
        offset: int,
        limit: int,
        inclusion: str = "all",
        last_result: str = "all",
        keyword: str = "",
    ) -> tuple[list[CoverageRow], int]:
        """分頁列出指定 schema 的來源表,附每表最新執行結果,套 inclusion / last_result / keyword。

        - inclusion: all / included(sync_excluded=false)/ excluded(sync_excluded=true)
        - last_result: all / success / failed / never(無任何 log)/(其餘 status 亦以字面比對)
        - keyword: 對 table_name 或 business_name 做 ILIKE 子字串比對(空字串不套)
        """
        # 每表最新 log 的 status(DISTINCT ON (schema, table) ORDER BY … pid DESC)
        latest_log = (
            select(
                EtlRunLog.source_schema.label("ls_schema"),
                EtlRunLog.source_table.label("ls_table"),
                EtlRunLog.status.label("last_status"),
            )
            .distinct(EtlRunLog.source_schema, EtlRunLog.source_table)
            .order_by(
                EtlRunLog.source_schema,
                EtlRunLog.source_table,
                EtlRunLog.pid.desc(),
            )
            .subquery()
        )

        conds: list[ColumnElement[bool]] = [
            RdsTableMeta.dataset == Dataset.SOURCE,
            RdsTableMeta.schema_name == schema,
            RdsTableMeta.is_deleted.is_(False),
        ]
        if inclusion == "included":
            conds.append(RdsTableMeta.sync_excluded.is_(False))
        elif inclusion == "excluded":
            conds.append(RdsTableMeta.sync_excluded.is_(True))

        if last_result == "never":
            conds.append(latest_log.c.last_status.is_(None))
        elif last_result != "all":
            conds.append(latest_log.c.last_status == last_result)

        keyword = keyword.strip()
        if keyword:
            # 跳脫 LIKE 萬用字元,讓輸入以字面比對(escape 反斜線自身在前)
            escaped = (
                keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            pattern = f"%{escaped}%"
            conds.append(
                or_(
                    RdsTableMeta.table_name.ilike(pattern, escape="\\"),
                    RdsTableMeta.business_name.ilike(pattern, escape="\\"),
                )
            )

        onclause = and_(
            latest_log.c.ls_schema == RdsTableMeta.schema_name,
            latest_log.c.ls_table == RdsTableMeta.table_name,
        )

        total = (
            await self._db.execute(
                select(func.count())
                .select_from(RdsTableMeta)
                .outerjoin(latest_log, onclause)
                .where(*conds)
            )
        ).scalar_one()

        stmt = (
            select(
                RdsTableMeta.uid,
                RdsTableMeta.schema_name,
                RdsTableMeta.table_name,
                RdsTableMeta.business_name,
                RdsTableMeta.sync_excluded,
                RdsTableMeta.last_synced_at,
                RdsTableMeta.row_count,
                latest_log.c.last_status,
            )
            .select_from(RdsTableMeta)
            .outerjoin(latest_log, onclause)
            .where(*conds)
            .order_by(RdsTableMeta.table_name)
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._db.execute(stmt)).all()
        return list(rows), int(total)

    async def latest_log_status(self, schema: str, table: str) -> str | None:
        """回指定表最新一筆 etl_run_logs 的 status;無 log 回 None。"""
        stmt = (
            select(EtlRunLog.status)
            .where(
                EtlRunLog.source_schema == schema,
                EtlRunLog.source_table == table,
            )
            .order_by(EtlRunLog.pid.desc())
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalars().first()

    async def find_meta_by_uid(self, uid: UUID) -> RdsTableMeta | None:
        """依 uid 取未刪除的表快照(dataset 不限)。"""
        return (
            await self._db.execute(
                select(RdsTableMeta).where(
                    RdsTableMeta.uid == uid,
                    RdsTableMeta.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()

    async def set_excluded(
        self, row: RdsTableMeta, excluded: bool, actor_uid: UUID
    ) -> None:
        """設定逐表排除旗標並更新異動欄位。"""
        row.sync_excluded = excluded
        row.updated_by = actor_uid
        row.updated_at = _db_now()
        await self._db.flush()
