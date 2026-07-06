"""快照服務:內省 RDS 結構 → JOIN DS 字典取業務中文名 → upsert rds_table_meta;
瀏覽 API 改讀快照(不即時打 RDS),熱點讀取加 Redis cache。

- `refresh(dataset)` 是唯一對 RDS 執行的路徑(唯讀內省 + 唯讀字典查詢),結果落自有 DB;
  **不寫 RDS**。JOIN GAT_FILE 僅於 refresh 執行一次。
- `list_schemas` / `list_tables` 讀自有 DB 快照 + Redis cache;refresh 後失效對應 dataset 快取。
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis as cache
from app.etl import introspect
from app.etl.dictionary import fetch_table_comment
from app.models.rds_table_meta import Dataset, RdsTableMeta
from app.repositories.rds_table_meta_repo import RdsTableMetaRepository
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
            collected: list[_CollectedTable] = []
            for t in tables:
                table_name = str(t["name"])
                business_name = await fetch_table_comment(conn, table_name)
                collected.append(
                    _CollectedTable(
                        schema_name=str(t["schema"]),
                        table_name=table_name,
                        business_name=business_name,
                        column_count=int(t["column_count"]),
                        row_count=int(t["row_count"]),
                    )
                )
        return collected

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
        hide_empty: bool,
    ) -> TableListResponse:
        key = cache.cache_key(
            "datasets", dataset_value, "tables", schema, page, page_size, int(hide_empty)
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
            hide_empty=hide_empty,
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
