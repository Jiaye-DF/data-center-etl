from collections.abc import Sequence
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, Row, and_, func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Dataset, EtlRun, EtlRunLog, EtlTable, RdsTableMeta, Schedule
from app.repositories.rds_table_meta_repo import _keyword_cond
from app.utils.datetime import db_now as _db_now

# list_tables_view 每列欄位(label):
# table_name, business_name, last_synced_at, row_count,
# schedule_uid, cron_expr, is_enabled, description, last_run_status
TablesViewRow = Row[
    tuple[
        str,
        str | None,
        datetime | None,
        int,
        UUID | None,
        str | None,
        bool | None,
        str | None,
        str | None,
    ]
]


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

    # ── v1.3.1 一表一排程:逐表讀寫 ─────────────────────────────────────
    async def find_by_source_table(self, schema: str, table: str) -> Schedule | None:
        """依 (source_schema, source_table) 於未刪除範圍找排程。"""
        stmt = select(Schedule).where(
            Schedule.source_schema == schema,
            Schedule.source_table == table,
            Schedule.is_deleted.is_(False),
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def upsert_for_source_table(
        self,
        *,
        schema: str,
        table: str,
        name: str,
        cron_expr: str,
        is_enabled: bool,
        actor_uid: UUID,
    ) -> Schedule:
        """一表一排程 upsert:無則建;有則不覆蓋既有啟停 / cron(避免快照重置使用者設定)。"""
        existing = await self.find_by_source_table(schema, table)
        if existing is not None:
            return existing
        schedule = Schedule(
            uid=uuid4(),
            name=name,
            cron_expr=cron_expr,
            is_enabled=is_enabled,
            etl_table_pid=None,
            source_schema=schema,
            source_table=table,
            description=None,
            created_by=actor_uid,
            updated_by=actor_uid,
        )
        self._db.add(schedule)
        await self._db.flush()
        return schedule

    async def soft_delete_by_source_tables_absent(
        self, present: set[tuple[str, str]], actor_uid: UUID
    ) -> int:
        """把 source_table 非 NULL 且 (schema, table) 不在 present 的排程軟刪(來源表消失)。"""
        stmt = select(Schedule).where(
            Schedule.is_deleted.is_(False),
            Schedule.source_table.is_not(None),
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        count = 0
        for schedule in rows:
            key = (str(schedule.source_schema), str(schedule.source_table))
            if key not in present:
                schedule.is_deleted = True
                schedule.updated_by = actor_uid
                schedule.updated_at = _db_now()
                count += 1
        await self._db.flush()
        return count

    async def soft_delete_legacy_all_table(self, actor_uid: UUID) -> int:
        """軟刪 v1.3.0 遺留「全表增量」排程(source_schema IS NULL AND is_deleted=false)。"""
        stmt = select(Schedule).where(
            Schedule.source_schema.is_(None),
            Schedule.is_deleted.is_(False),
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        count = 0
        for schedule in rows:
            schedule.is_deleted = True
            schedule.updated_by = actor_uid
            schedule.updated_at = _db_now()
            count += 1
        await self._db.flush()
        return count

    # ── v1.3.1 逐表視角查詢 ────────────────────────────────────────────
    async def list_tables_view(
        self,
        *,
        schema: str,
        offset: int,
        limit: int,
        enabled: str = "all",
        last_result: str = "all",
        keyword: str = "",
        exact: bool = False,
    ) -> tuple[list[TablesViewRow], int]:
        """分頁列出指定 schema 的來源表,LEFT JOIN 其排程與每表最新執行結果。

        - enabled: all / enabled(is_enabled=true)/ disabled(is_enabled 非 true,含無排程)
        - last_result: all / success / failed / never(無任何 log)/(其餘 status 亦以字面比對)
        - keyword: 空字串不套;exact=False 對 table_name / business_name ILIKE 子字串,
          exact=True(下拉選定某表)則 table_name 精準等值
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
        # 一表一排程:依 (source_schema, source_table) LEFT JOIN;is_deleted 條件入 ON 保 LEFT 語意
        sched_on = and_(
            Schedule.source_schema == RdsTableMeta.schema_name,
            Schedule.source_table == RdsTableMeta.table_name,
            Schedule.is_deleted.is_(False),
        )
        log_on = and_(
            latest_log.c.ls_schema == RdsTableMeta.schema_name,
            latest_log.c.ls_table == RdsTableMeta.table_name,
        )

        conds: list[ColumnElement[bool]] = [
            RdsTableMeta.dataset == Dataset.SOURCE,
            RdsTableMeta.schema_name == schema,
            RdsTableMeta.is_deleted.is_(False),
        ]
        if enabled == "enabled":
            conds.append(Schedule.is_enabled.is_(True))
        elif enabled == "disabled":
            conds.append(Schedule.is_enabled.is_not(True))

        if last_result == "never":
            conds.append(latest_log.c.last_status.is_(None))
        elif last_result != "all":
            conds.append(latest_log.c.last_status == last_result)

        keyword = keyword.strip()
        if keyword:
            conds.append(_keyword_cond(keyword, exact))

        total = (
            await self._db.execute(
                select(func.count())
                .select_from(RdsTableMeta)
                .outerjoin(Schedule, sched_on)
                .outerjoin(latest_log, log_on)
                .where(*conds)
            )
        ).scalar_one()

        stmt = (
            select(
                RdsTableMeta.table_name.label("table_name"),
                RdsTableMeta.business_name.label("business_name"),
                RdsTableMeta.last_synced_at.label("last_synced_at"),
                RdsTableMeta.row_count.label("row_count"),
                Schedule.uid.label("schedule_uid"),
                Schedule.cron_expr.label("cron_expr"),
                Schedule.is_enabled.label("is_enabled"),
                Schedule.description.label("description"),
                latest_log.c.last_status.label("last_run_status"),
            )
            .select_from(RdsTableMeta)
            .outerjoin(Schedule, sched_on)
            .outerjoin(latest_log, log_on)
            .where(*conds)
            .order_by(RdsTableMeta.table_name)
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._db.execute(stmt)).all()
        return list(rows), int(total)

    async def list_schema_summaries(self) -> list[tuple[str, int, int]]:
        """聚合來源表各 schema 的 (表數, 已啟用排程數),未刪除範圍,依 schema 名排序。"""
        table_stmt = (
            select(RdsTableMeta.schema_name, func.count())
            .where(
                RdsTableMeta.dataset == Dataset.SOURCE,
                RdsTableMeta.is_deleted.is_(False),
            )
            .group_by(RdsTableMeta.schema_name)
            .order_by(RdsTableMeta.schema_name)
        )
        table_rows = (await self._db.execute(table_stmt)).all()

        enabled_stmt = (
            select(Schedule.source_schema, func.count())
            .where(
                Schedule.is_deleted.is_(False),
                Schedule.is_enabled.is_(True),
                Schedule.source_table.is_not(None),
            )
            .group_by(Schedule.source_schema)
        )
        enabled_rows = (await self._db.execute(enabled_stmt)).all()
        enabled_by_schema = {
            str(schema): int(count) for schema, count in enabled_rows
        }
        return [
            (str(schema), int(count), enabled_by_schema.get(str(schema), 0))
            for schema, count in table_rows
        ]

    async def batch_set_enabled(
        self,
        *,
        schema: str | None,
        enabled: bool,
        only_source_tables: bool,
        actor_uid: UUID,
        filter_enabled: str = "all",
        filter_last_result: str = "all",
        filter_keyword: str = "",
        filter_keyword_exact: bool = False,
    ) -> int:
        """批次設 is_enabled,回實際變更筆數;可依逐表列表相同的篩選限縮命中表。

        - schema=None 為全部 schema;only_source_tables=True 僅限有 source_table 的排程。
        - filter_enabled: all / enabled / disabled(對排程當下 is_enabled)。
        - filter_last_result: all / success / failed / never(對每表最新 etl_run_logs)。
        - filter_keyword: 空字串不套;exact=False 對 table_name / business_name ILIKE,
          exact=True(下拉選定某表)則 table_name 精準等值。
          篩選皆 all / 空 時等同「(該 schema 或全部)全部來源表排程」。
        """
        conds: list[ColumnElement[bool]] = [
            Schedule.is_deleted.is_(False),
            # 僅更新狀態實際改變者 → 回傳筆數即變更筆數
            Schedule.is_enabled.is_not(enabled),
        ]
        if only_source_tables:
            conds.append(Schedule.source_table.is_not(None))
        if schema is not None:
            conds.append(Schedule.source_schema == schema)
        if filter_enabled == "enabled":
            conds.append(Schedule.is_enabled.is_(True))
        elif filter_enabled == "disabled":
            conds.append(Schedule.is_enabled.is_not(True))

        keyword = filter_keyword.strip()
        if keyword or filter_last_result != "all":
            # 關鍵字 / 上次結果篩選走 rds_table_meta × 每表最新 log → 取命中表 (schema, table)
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
            meta_conds: list[ColumnElement[bool]] = [
                RdsTableMeta.dataset == Dataset.SOURCE,
                RdsTableMeta.is_deleted.is_(False),
            ]
            if schema is not None:
                meta_conds.append(RdsTableMeta.schema_name == schema)
            if filter_last_result == "never":
                meta_conds.append(latest_log.c.last_status.is_(None))
            elif filter_last_result != "all":
                meta_conds.append(latest_log.c.last_status == filter_last_result)
            if keyword:
                meta_conds.append(_keyword_cond(keyword, filter_keyword_exact))
            matching = (
                select(RdsTableMeta.schema_name, RdsTableMeta.table_name)
                .select_from(RdsTableMeta)
                .outerjoin(
                    latest_log,
                    and_(
                        latest_log.c.ls_schema == RdsTableMeta.schema_name,
                        latest_log.c.ls_table == RdsTableMeta.table_name,
                    ),
                )
                .where(*meta_conds)
            )
            conds.append(
                tuple_(Schedule.source_schema, Schedule.source_table).in_(matching)
            )

        result = await self._db.execute(
            update(Schedule)
            .where(*conds)
            .values(is_enabled=enabled, updated_by=actor_uid, updated_at=_db_now())
        )
        await self._db.flush()
        return int(result.rowcount)
