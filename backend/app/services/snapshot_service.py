"""快照服務:內省 RDS 結構 → JOIN DS 字典取業務中文名 → upsert rds_table_meta;
瀏覽 API 改讀快照(不即時打 RDS),熱點讀取加 Redis cache。

- `refresh(dataset)` 是唯一對 RDS 執行的路徑(唯讀內省 + 唯讀字典查詢),結果落自有 DB;
  **不寫 RDS**。JOIN GAT_FILE 僅於 refresh 執行一次。
- `list_schemas` / `list_tables` 讀自有 DB 快照 + Redis cache;refresh 後失效對應 dataset 快取。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis as cache
from app.etl import introspect
from app.etl.dictionary import fetch_table_comments
from app.models.rds_table_meta import Dataset, RdsTableMeta
from app.repositories.rds_table_meta_repo import RdsTableMetaRepository
from app.repositories.schedule_repo import ScheduleRepository
from app.schemas.rawdata import (
    SchemaListResponse,
    SchemaSummary,
    SnapshotRefreshResponse,
    TableListResponse,
    TableSummary,
)
from app.utils.datetime import db_now

# cache TTL:快照為手動 refresh 觸發,短 TTL 防髒讀無限存活即可
_CACHE_TTL_SECONDS = 300

# 自動建排程為系統動作,無登入使用者 → 全零 UUID 系統帳號(同 worker / audit_service 約定)
_SYSTEM_ACTOR_UID = UUID("00000000-0000-0000-0000-000000000000")
# 逐表排程預設:每天 00:00(Asia/Taipei)、停用(避免快照納入即自動排程執行)
_AUTO_SCHEDULE_CRON = "0 0 * * *"


@dataclass(frozen=True)
class TableFilters:
    """list_tables 進階篩選條件;截止日為 naive UTC+8 上界(含當日)。

    rows: all / nonempty / empty;synced / transformed: all / (un)synced / (un)transformed;
    *_before 搭配狀態 → 「是否在該日前(含)同步/轉換」。
    """

    rows: str = "nonempty"
    synced: str = "all"
    transformed: str = "all"
    synced_before: datetime | None = None
    transformed_before: datetime | None = None
    keyword: str = ""
    # True=下拉選定某表(table_name 精準等值);False=自由輸入(table_name / business_name 子字串)
    exact: bool = False

    def cache_fragment(self) -> tuple[str, ...]:
        """組 cache key 用的穩定片段(None 截止日以 '-' 佔位)。"""

        def ts(value: datetime | None) -> str:
            return value.isoformat() if value is not None else "-"

        return (
            self.rows,
            self.synced,
            self.transformed,
            ts(self.synced_before),
            ts(self.transformed_before),
            self.keyword,
            "exact" if self.exact else "fuzzy",
        )


@dataclass(frozen=True)
class _CollectedTable:
    """單表內省結果 + 字典業務名(refresh 落地前的中間結構)。"""

    schema_name: str
    table_name: str
    business_name: str | None
    column_count: int
    row_count: int


class SnapshotService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = RdsTableMetaRepository(db)
        self._schedule_repo = ScheduleRepository(db)

    # ── refresh(唯一打 RDS 的路徑)──────────────────────────────────────
    async def refresh(self, dataset_value: str, actor_uid: UUID) -> SnapshotRefreshResponse:
        """內省 dataset RDS + 字典查業務名 → upsert 快照 → 失效對應 cache → 回統計。"""
        dataset = Dataset(dataset_value)
        snapshot_at = db_now()
        collected = await self._collect_from_rds(dataset_value)
        for item in collected:
            await self._repo.upsert_snapshot(
                dataset=dataset,
                schema_name=item.schema_name,
                table_name=item.table_name,
                business_name=item.business_name,
                column_count=item.column_count,
                row_count=item.row_count,
                snapshot_at=snapshot_at,
                actor_uid=actor_uid,
            )
        # 僅 source:同交易維護逐表排程(避免「表有快照、無排程」中間態)
        if dataset is Dataset.SOURCE:
            await self._sync_source_schedules(collected)
        await cache.delete_pattern(cache.cache_key("datasets", dataset_value, "*"))
        return SnapshotRefreshResponse(
            dataset=dataset_value,
            table_count=len(collected),
            snapshot_at=snapshot_at,
        )

    async def _collect_from_rds(self, dataset_value: str) -> list[_CollectedTable]:
        """同一連線內:內省全 schema 全表(唯讀)+ 逐表查 DS 字典 GAT_FILE 業務名(唯讀)。"""
        engine = introspect.get_engine(dataset_value)
        async with engine.connect() as conn:
            tables = await introspect.snapshot_tables(conn)
            # 批量查全部表名的字典業務名(一次 RDS 來回,取代逐表 N 次)
            names = [str(t["name"]) for t in tables]
            comments = await fetch_table_comments(conn, names)
            collected: list[_CollectedTable] = [
                _CollectedTable(
                    schema_name=str(t["schema"]),
                    table_name=str(t["name"]),
                    business_name=comments.get(str(t["name"]).lower()),
                    column_count=int(t["column_count"]),
                    row_count=int(t["row_count"]),
                )
                for t in tables
            ]
        return collected

    async def _sync_source_schedules(self, collected: list[_CollectedTable]) -> None:
        """本輪來源表逐表建/留排程 + 收斂:缺表軟刪、v1.3.0 全表舊排程一次性軟刪。

        冪等可重入:既有排程不覆蓋啟停 / cron;與 metadata upsert 同交易提交。
        """
        present: set[tuple[str, str]] = set()
        for item in collected:
            present.add((item.schema_name, item.table_name))
            await self._schedule_repo.upsert_for_source_table(
                schema=item.schema_name,
                table=item.table_name,
                name=f"{item.schema_name}.{item.table_name}",
                cron_expr=_AUTO_SCHEDULE_CRON,
                is_enabled=False,
                actor_uid=_SYSTEM_ACTOR_UID,
            )
        await self._schedule_repo.soft_delete_by_source_tables_absent(
            present=present, actor_uid=_SYSTEM_ACTOR_UID
        )
        await self._schedule_repo.soft_delete_legacy_all_table(
            actor_uid=_SYSTEM_ACTOR_UID
        )

    # ── 讀快照(cache 命中免打 repo)─────────────────────────────────────
    async def list_schemas(self, dataset_value: str) -> SchemaListResponse:
        key = cache.cache_key("datasets", dataset_value, "schemas")
        cached = await cache.cache_get(key)
        if cached is not None:
            return SchemaListResponse.model_validate_json(cached)
        rows = await self._repo.list_schemas(Dataset(dataset_value))
        response = SchemaListResponse(
            items=[
                SchemaSummary(schema=schema, table_count=count) for schema, count in rows
            ]
        )
        await cache.cache_set(
            key, response.model_dump_json(), ttl_seconds=_CACHE_TTL_SECONDS
        )
        return response

    async def list_tables(
        self,
        dataset_value: str,
        schema: str,
        *,
        page: int,
        page_size: int,
        filters: TableFilters,
    ) -> TableListResponse:
        key = cache.cache_key(
            "datasets",
            dataset_value,
            "tables",
            schema,
            page,
            page_size,
            *filters.cache_fragment(),
        )
        cached = await cache.cache_get(key)
        if cached is not None:
            return TableListResponse.model_validate_json(cached)
        offset = (page - 1) * page_size
        rows, total = await self._repo.list_by_schema(
            Dataset(dataset_value),
            schema,
            offset=offset,
            limit=page_size,
            rows=filters.rows,
            synced=filters.synced,
            transformed=filters.transformed,
            synced_before=filters.synced_before,
            transformed_before=filters.transformed_before,
            keyword=filters.keyword,
            exact=filters.exact,
        )
        response = TableListResponse(
            items=[self._to_summary(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )
        await cache.cache_set(
            key, response.model_dump_json(), ttl_seconds=_CACHE_TTL_SECONDS
        )
        return response

    @staticmethod
    def _to_summary(row: RdsTableMeta) -> TableSummary:
        return TableSummary(
            name=row.table_name,
            business_name=row.business_name,
            column_count=row.column_count,
            row_count=row.row_count,
            last_synced_at=row.last_synced_at,
            last_transformed_at=row.last_transformed_at,
        )
