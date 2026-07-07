"""rds_table_meta 快照 repo:upsert 快照、分頁讀取、聚合 schema、標記同步 / 轉換時間。

- 唯一鍵 (dataset, schema_name, table_name) 為 partial unique index(is_deleted=false);
  upsert 以未刪除範圍 find-or-create。
- 讀取一律過濾 is_deleted(軟刪除規範 `04-databases/02-soft-delete.md`);
  不過濾版另加 `_including_deleted` 後綴(目前無需求,不預先實作)。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models.rds_table_meta import Dataset, RdsTableMeta
from app.utils.datetime import db_now as _db_now


class RdsTableMetaRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def upsert_snapshot(
        self,
        *,
        dataset: Dataset,
        schema_name: str,
        table_name: str,
        business_name: str | None,
        column_count: int,
        row_count: int,
        snapshot_at: datetime,
        actor_uid: UUID,
    ) -> RdsTableMeta:
        """依 (dataset, schema, table) find-or-create;既有筆更新結構 / 業務名 / 快照時間。"""
        existing = (
            await self._db.execute(
                select(RdsTableMeta).where(
                    RdsTableMeta.dataset == dataset,
                    RdsTableMeta.schema_name == schema_name,
                    RdsTableMeta.table_name == table_name,
                    RdsTableMeta.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            row = RdsTableMeta(
                uid=uuid4(),
                dataset=dataset,
                schema_name=schema_name,
                table_name=table_name,
                business_name=business_name,
                column_count=column_count,
                row_count=row_count,
                snapshot_at=snapshot_at,
                created_by=actor_uid,
                updated_by=actor_uid,
            )
            self._db.add(row)
            await self._db.flush()
            return row
        existing.business_name = business_name
        existing.column_count = column_count
        existing.row_count = row_count
        existing.snapshot_at = snapshot_at
        existing.updated_by = actor_uid
        existing.updated_at = _db_now()
        await self._db.flush()
        return existing

    async def list_schemas(self, dataset: Dataset) -> list[tuple[str, int]]:
        """聚合 dataset 下各 schema 的表數(未刪除範圍),依 schema 名排序。"""
        stmt = (
            select(RdsTableMeta.schema_name, func.count())
            .where(
                RdsTableMeta.dataset == dataset,
                RdsTableMeta.is_deleted.is_(False),
            )
            .group_by(RdsTableMeta.schema_name)
            .order_by(RdsTableMeta.schema_name)
        )
        rows = (await self._db.execute(stmt)).all()
        return [(str(schema), int(count)) for schema, count in rows]

    @staticmethod
    def _presence_cutoff(
        column: InstrumentedAttribute[datetime | None],
        want_present: bool | None,
        before: datetime | None,
    ) -> ColumnElement[bool] | None:
        """「是否在截止日前有值」條件;want_present=None(全部)回 None 不加條件。

        - want_present=True(已同步/已轉換):有截止日 → column <= before(<= 已隱含 NOT NULL);
          無截止日 → column IS NOT NULL
        - want_present=False(未同步/未轉換):有截止日 → 到該日仍無
          = column IS NULL OR column > before;無截止日 → column IS NULL
        """
        if want_present is None:
            return None
        if want_present:
            return column <= before if before is not None else column.is_not(None)
        if before is not None:
            return or_(column.is_(None), column > before)
        return column.is_(None)

    async def list_by_schema(
        self,
        dataset: Dataset,
        schema: str,
        *,
        offset: int,
        limit: int,
        rows: str = "nonempty",
        synced: str = "all",
        transformed: str = "all",
        synced_before: datetime | None = None,
        transformed_before: datetime | None = None,
        keyword: str = "",
    ) -> tuple[list[RdsTableMeta], int]:
        """分頁列出指定 schema 的表,套進階篩選(狀態分段 + 截止日 + 關鍵字,AND 疊加)。

        - rows: all / nonempty(row_count>0)/ empty(row_count=0)
        - synced / transformed: all / 有值 / 無值(搭配截止日 → 「是否在該日前(含)同步/轉換」)
        - *_before: 截止日上界(含);state=all 時忽略
        - keyword: 對 table_name 或 business_name 做 ILIKE 子字串比對(空字串不套)
        """
        conds: list[ColumnElement[bool]] = [
            RdsTableMeta.dataset == dataset,
            RdsTableMeta.schema_name == schema,
            RdsTableMeta.is_deleted.is_(False),
        ]
        if rows == "nonempty":
            conds.append(RdsTableMeta.row_count > 0)
        elif rows == "empty":
            conds.append(RdsTableMeta.row_count == 0)
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
        synced_present = {"synced": True, "unsynced": False}.get(synced)
        transformed_present = {"transformed": True, "untransformed": False}.get(
            transformed
        )
        for cond in (
            self._presence_cutoff(
                RdsTableMeta.last_synced_at, synced_present, synced_before
            ),
            self._presence_cutoff(
                RdsTableMeta.last_transformed_at,
                transformed_present,
                transformed_before,
            ),
        ):
            if cond is not None:
                conds.append(cond)
        total = (
            await self._db.execute(
                select(func.count()).select_from(RdsTableMeta).where(*conds)
            )
        ).scalar_one()
        result = (
            await self._db.execute(
                select(RdsTableMeta)
                .where(*conds)
                .order_by(RdsTableMeta.table_name)
                .offset(offset)
                .limit(limit)
            )
        ).scalars()
        return list(result.all()), total

    async def mark_synced(
        self,
        dataset: Dataset,
        schema_name: str,
        table_name: str,
        *,
        actor_uid: UUID,
        when: datetime | None = None,
    ) -> None:
        """標記單表最近從 RDS 同步到 hub 的時間(供同步鏈記錄)。"""
        moment = when or _db_now()
        await self._db.execute(
            update(RdsTableMeta)
            .where(
                RdsTableMeta.dataset == dataset,
                RdsTableMeta.schema_name == schema_name,
                RdsTableMeta.table_name == table_name,
                RdsTableMeta.is_deleted.is_(False),
            )
            .values(last_synced_at=moment, updated_by=actor_uid, updated_at=_db_now())
        )
        await self._db.flush()

    async def mark_transformed(
        self,
        dataset: Dataset,
        schema_name: str,
        table_name: str,
        *,
        actor_uid: UUID,
        when: datetime | None = None,
    ) -> None:
        """標記單表最近套字典 COMMENT(轉換)的時間(供同步鏈記錄)。"""
        moment = when or _db_now()
        await self._db.execute(
            update(RdsTableMeta)
            .where(
                RdsTableMeta.dataset == dataset,
                RdsTableMeta.schema_name == schema_name,
                RdsTableMeta.table_name == table_name,
                RdsTableMeta.is_deleted.is_(False),
            )
            .values(last_transformed_at=moment, updated_by=actor_uid, updated_at=_db_now())
        )
        await self._db.flush()

    async def read_stat_baselines(
        self, dataset: Dataset
    ) -> dict[tuple[str, str], tuple[int, int, int] | None]:
        """讀各表 signature 基準;三欄任一為 NULL(尚無基準)該表回 None(task-004 視為變動)。
        僅未刪除範圍。回 {(schema, table): (ins, upd, del) 或 None}。"""
        stmt = select(
            RdsTableMeta.schema_name,
            RdsTableMeta.table_name,
            RdsTableMeta.last_stat_ins,
            RdsTableMeta.last_stat_upd,
            RdsTableMeta.last_stat_del,
        ).where(
            RdsTableMeta.dataset == dataset,
            RdsTableMeta.is_deleted.is_(False),
        )
        rows = (await self._db.execute(stmt)).all()
        baselines: dict[tuple[str, str], tuple[int, int, int] | None] = {}
        for schema, table, ins, upd, dele in rows:
            key = (str(schema), str(table))
            if ins is None or upd is None or dele is None:
                baselines[key] = None
            else:
                baselines[key] = (int(ins), int(upd), int(dele))
        return baselines

    async def update_stat_signature(
        self,
        dataset: Dataset,
        schema_name: str,
        table_name: str,
        *,
        n_tup_ins: int,
        n_tup_upd: int,
        n_tup_del: int,
        actor_uid: UUID,
    ) -> None:
        """整批覆蓋成功後,把該表 signature 基準更新為當下來源計數器(供下輪比對)。"""
        await self._db.execute(
            update(RdsTableMeta)
            .where(
                RdsTableMeta.dataset == dataset,
                RdsTableMeta.schema_name == schema_name,
                RdsTableMeta.table_name == table_name,
                RdsTableMeta.is_deleted.is_(False),
            )
            .values(
                last_stat_ins=n_tup_ins,
                last_stat_upd=n_tup_upd,
                last_stat_del=n_tup_del,
                updated_by=actor_uid,
                updated_at=_db_now(),
            )
        )
        await self._db.flush()

    async def list_excluded(self, dataset: Dataset) -> set[tuple[str, str]]:
        """回被逐表排除(sync_excluded=true)的表集合;未刪除範圍。"""
        stmt = select(RdsTableMeta.schema_name, RdsTableMeta.table_name).where(
            RdsTableMeta.dataset == dataset,
            RdsTableMeta.is_deleted.is_(False),
            RdsTableMeta.sync_excluded.is_(True),
        )
        rows = (await self._db.execute(stmt)).all()
        return {(str(schema), str(table)) for schema, table in rows}
