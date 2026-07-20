"""rds_table_meta 快照 repo:upsert 快照、分頁讀取、聚合 schema、標記同步 / 轉換時間。

- 唯一鍵 (dataset, schema_name, table_name) 為 partial unique index(is_deleted=false);
  upsert 以未刪除範圍 find-or-create。
- 讀取一律過濾 is_deleted(軟刪除規範 `04-databases/02-soft-delete.md`);
  不過濾版另加 `_including_deleted` 後綴(目前無需求,不預先實作)。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models.rds_table_meta import Dataset, RdsTableMeta
from app.utils.datetime import db_now as _db_now

# 「未分類」模組哨符值(module_code IS NULL);與前端 DatasetBrowser.tsx 的
# UNCLASSIFIED_MODULE 常值對齊(AD-115/117:後端不支援 IS NULL 等值篩選的補洞)。
UNCLASSIFIED_MODULE_SENTINEL = "__unclassified__"


def _keyword_cond(keyword: str, exact: bool) -> ColumnElement[bool]:
    """關鍵字比對條件(呼叫端須先確認 keyword 非空)。

    - exact=True:下拉選定某表 → table_name 精準等值(不會被子字串誤命中他表)
    - exact=False:自由輸入 → table_name / business_name ILIKE 子字串(跳脫 LIKE 萬用字元)
    """
    if exact:
        return RdsTableMeta.table_name == keyword
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    return or_(
        RdsTableMeta.table_name.ilike(pattern, escape="\\"),
        RdsTableMeta.business_name.ilike(pattern, escape="\\"),
    )


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
        module_code: str | None = None,
    ) -> RdsTableMeta:
        """依 (dataset, schema, table) find-or-create;
        既有筆更新結構 / 業務名 / 模組代碼 / 快照時間。"""
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
                module_code=module_code,
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
        existing.module_code = module_code
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

    async def list_distinct_modules(
        self, dataset: Dataset, schema: str
    ) -> tuple[list[str], bool]:
        """回指定 schema 下 distinct module_code(排序)+ 是否存在未分類(module_code
        IS NULL)的表(未刪除範圍)。

        AD-115:聚合來源為整個 schema(非單頁),供模組篩選下拉取代「僅第 1 頁 distinct」
        的作法,避免分頁外模組無法被篩選。
        """
        stmt = (
            select(RdsTableMeta.module_code)
            .where(
                RdsTableMeta.dataset == dataset,
                RdsTableMeta.schema_name == schema,
                RdsTableMeta.is_deleted.is_(False),
            )
            .distinct()
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        codes = sorted({str(r) for r in rows if r is not None})
        has_unclassified = any(r is None for r in rows)
        return codes, has_unclassified

    async def summary_by_schema(
        self, dataset: Dataset, schema: str
    ) -> tuple[int, int, int, int]:
        """回指定 schema 的表數分布(未刪除範圍):
        (總表數, 有資料表數 row_count>0, 空表數 row_count=0, 1000+ 表數 row_count>1000)。

        不做 row_count 加總 — row_count 為 bounded 探測(>1000 存 1001),加總會失真;
        改以「表數分布 + 1000+ 桶」提供可信概覽。
        """
        stmt = select(
            func.count(),
            func.count(case((RdsTableMeta.row_count > 0, 1))),
            func.count(case((RdsTableMeta.row_count == 0, 1))),
            func.count(case((RdsTableMeta.row_count > 1000, 1))),
        ).where(
            RdsTableMeta.dataset == dataset,
            RdsTableMeta.schema_name == schema,
            RdsTableMeta.is_deleted.is_(False),
        )
        total, nonempty, empty, capped = (await self._db.execute(stmt)).one()
        return int(total), int(nonempty), int(empty), int(capped)

    async def dataset_scale(
        self, dataset: Dataset
    ) -> tuple[int, int, int, datetime | None, datetime | None]:
        """儀表板用:回 dataset 規模 + 新鮮度(未刪除範圍):
        (總表數, 有資料表數, 空表數, 最近快照時間, 最近同步時間)。"""
        stmt = select(
            func.count(),
            func.count(case((RdsTableMeta.row_count > 0, 1))),
            func.count(case((RdsTableMeta.row_count == 0, 1))),
            func.max(RdsTableMeta.snapshot_at),
            func.max(RdsTableMeta.last_synced_at),
        ).where(
            RdsTableMeta.dataset == dataset,
            RdsTableMeta.is_deleted.is_(False),
        )
        total, nonempty, empty, snap, synced = (await self._db.execute(stmt)).one()
        return int(total), int(nonempty), int(empty), snap, synced

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
        exact: bool = False,
        row_min: int | None = None,
        row_max: int | None = None,
        module: str = "",
    ) -> tuple[list[RdsTableMeta], int]:
        """分頁列出指定 schema 的表,套進階篩選(狀態分段 + 截止日 + 關鍵字 + 筆數區間 + 模組,
        AND 疊加)。

        - rows: all / nonempty(row_count>0)/ empty(row_count=0)
        - row_min / row_max: 資料總筆數區間(含端點);None 為該端不限
          (注意 row_count 上限探測到 1001,>1000 一律存 1001,故 >1000 無法精確區分)
        - synced / transformed: all / 有值 / 無值(搭配截止日 → 「是否在該日前(含)同步/轉換」)
        - *_before: 截止日上界(含);state=all 時忽略
        - keyword: 空字串不套;exact=False 對 table_name 或 business_name ILIKE 子字串比對,
          exact=True(下拉選定某表)則對 table_name 精準等值,避免子字串誤命中他表
        - module: 空字串不套;`UNCLASSIFIED_MODULE_SENTINEL` 篩 module_code IS NULL
          (AD-117);其餘非空值對 module_code 精準等值(task-007 B2)
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
        if row_min is not None:
            conds.append(RdsTableMeta.row_count >= row_min)
        if row_max is not None:
            conds.append(RdsTableMeta.row_count <= row_max)
        keyword = keyword.strip()
        if keyword:
            conds.append(_keyword_cond(keyword, exact))
        module = module.strip()
        if module == UNCLASSIFIED_MODULE_SENTINEL:
            conds.append(RdsTableMeta.module_code.is_(None))
        elif module:
            conds.append(RdsTableMeta.module_code == module)
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
