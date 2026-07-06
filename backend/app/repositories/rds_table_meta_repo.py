"""rds_table_meta 快照 repo:upsert 快照、分頁讀取、聚合 schema、標記同步 / 轉換時間。

- 唯一鍵 (dataset, schema_name, table_name) 為 partial unique index(is_deleted=false);
  upsert 以未刪除範圍 find-or-create。
- 讀取一律過濾 is_deleted(軟刪除規範 `04-databases/02-soft-delete.md`);
  不過濾版另加 `_including_deleted` 後綴(目前無需求,不預先實作)。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def list_by_schema(
        self,
        dataset: Dataset,
        schema: str,
        *,
        offset: int,
        limit: int,
        hide_empty: bool,
    ) -> tuple[list[RdsTableMeta], int]:
        """分頁列出指定 schema 的表;hide_empty 過濾 row_count=0。"""
        conds = [
            RdsTableMeta.dataset == dataset,
            RdsTableMeta.schema_name == schema,
            RdsTableMeta.is_deleted.is_(False),
        ]
        if hide_empty:
            conds.append(RdsTableMeta.row_count > 0)
        total = (
            await self._db.execute(
                select(func.count()).select_from(RdsTableMeta).where(*conds)
            )
        ).scalar_one()
        rows = (
            await self._db.execute(
                select(RdsTableMeta)
                .where(*conds)
                .order_by(RdsTableMeta.table_name)
                .offset(offset)
                .limit(limit)
            )
        ).scalars()
        return list(rows.all()), total

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
