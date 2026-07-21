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
from app.core.exceptions import AppError
from app.etl import introspect
from app.etl.dictionary import fetch_table_comments, fetch_table_modules
from app.models.rds_table_meta import Dataset, RdsTableMeta
from app.repositories.rds_table_meta_repo import RdsTableMetaRepository
from app.repositories.schedule_repo import ScheduleRepository
from app.schemas.rawdata import (
    ModuleListResponse,
    SchemaListResponse,
    SchemaStatSummary,
    SchemaSummary,
    SnapshotRefreshProgress,
    SnapshotRefreshResponse,
    TableListResponse,
    TableSummary,
)
from app.utils.datetime import db_now

# cache TTL:快照為手動 refresh 觸發,短 TTL 防髒讀無限存活即可
_CACHE_TTL_SECONDS = 300

# refresh 進度 key TTL:refresh 異常中斷未清 key 時,靠 TTL 自然過期(不會卡住前端進度條)
_PROGRESS_TTL_SECONDS = 600
# persist 階段每 N 表回報一次進度(逐表回報會多打上萬次 Redis)
_PROGRESS_PERSIST_STEP = 200

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
    # 資料總筆數區間(含端點);None 為該端不限(row_count 上限探測 1001,>1000 無法精確)
    row_min: int | None = None
    row_max: int | None = None
    # ERP 模組代碼精準篩選(空字串=不篩;task-007 B2,資料集頁模組分類)
    module: str = ""

    def cache_fragment(self) -> tuple[str, ...]:
        """組 cache key 用的穩定片段(None 截止日以 '-' 佔位)。"""

        def ts(value: datetime | None) -> str:
            return value.isoformat() if value is not None else "-"

        def num(value: int | None) -> str:
            return str(value) if value is not None else "-"

        return (
            self.rows,
            self.synced,
            self.transformed,
            ts(self.synced_before),
            ts(self.transformed_before),
            self.keyword,
            "exact" if self.exact else "fuzzy",
            num(self.row_min),
            num(self.row_max),
            self.module,
        )


@dataclass(frozen=True)
class _CollectedTable:
    """單表內省結果 + 字典業務名(refresh 落地前的中間結構)。"""

    schema_name: str
    table_name: str
    business_name: str | None
    column_count: int
    row_count: int
    # 尾端加新欄 + 給預設值:既有測試以位置引數建構 _CollectedTable 者不受影響
    module_code: str | None = None


class SnapshotService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = RdsTableMetaRepository(db)
        self._schedule_repo = ScheduleRepository(db)

    # ── refresh(唯一打 RDS 的路徑)──────────────────────────────────────
    async def refresh(self, dataset_value: str, actor_uid: UUID) -> SnapshotRefreshResponse:
        """內省 dataset RDS + 字典查業務名 → upsert 快照 → 失效對應 cache → 回統計。

        全程把階段進度寫 Redis(`_report_progress`),供 `get_refresh_progress` 輪詢;
        結束(含異常)一律清進度 key,異常中斷漏清靠 TTL 過期。
        同 dataset 併發 refresh 以 SET NX 鎖互斥(AD-120):取不到鎖回 409。
        """
        dataset = Dataset(dataset_value)
        lock_key = self._lock_key(dataset_value)
        if not await cache.cache_set_nx(lock_key, "1", ttl_seconds=_PROGRESS_TTL_SECONDS):
            raise AppError("快照同步進行中,請稍後再試", response_code=409, status_code=409)
        snapshot_at = db_now()
        try:
            try:
                await self._report_progress(dataset_value, "introspect", 0, 0)
                collected = await self._collect_from_rds(dataset_value)
                total = len(collected)
                await self._report_progress(dataset_value, "persist", 0, total)
                for index, item in enumerate(collected, start=1):
                    await self._repo.upsert_snapshot(
                        dataset=dataset,
                        schema_name=item.schema_name,
                        table_name=item.table_name,
                        business_name=item.business_name,
                        module_code=item.module_code,
                        column_count=item.column_count,
                        row_count=item.row_count,
                        snapshot_at=snapshot_at,
                        actor_uid=actor_uid,
                    )
                    if index % _PROGRESS_PERSIST_STEP == 0 or index == total:
                        await self._report_progress(dataset_value, "persist", index, total)
                # 僅 source:同交易維護逐表排程(避免「表有快照、無排程」中間態)
                if dataset is Dataset.SOURCE:
                    await self._report_progress(dataset_value, "schedules", 0, total)
                    await self._sync_source_schedules(collected)
                await cache.delete_pattern(cache.cache_key("datasets", dataset_value, "*"))
            finally:
                await cache.cache_delete(self._progress_key(dataset_value))
        finally:
            await cache.cache_delete(lock_key)
        return SnapshotRefreshResponse(
            dataset=dataset_value,
            table_count=len(collected),
            snapshot_at=snapshot_at,
        )

    # ── refresh 進度(Redis;供前端輪詢進度條)────────────────────────────
    # key 刻意不落在 `datasets:*`(該 pattern 於 mirror_sync 收尾 / refresh 後整批失效,
    # 會誤刪進行中的進度;AD-119,對齊 tasks.py APPLY_PROGRESS_KEY 設計)
    @staticmethod
    def _progress_key(dataset_value: str) -> str:
        return cache.cache_key("snapshot-progress", dataset_value)

    @staticmethod
    def _lock_key(dataset_value: str) -> str:
        return cache.cache_key("snapshot-progress", dataset_value, "lock")

    async def _report_progress(
        self, dataset_value: str, phase: str, done: int, total: int
    ) -> None:
        payload = SnapshotRefreshProgress(active=True, phase=phase, done=done, total=total)
        await cache.cache_set(
            self._progress_key(dataset_value),
            payload.model_dump_json(),
            ttl_seconds=_PROGRESS_TTL_SECONDS,
        )

    @staticmethod
    async def get_refresh_progress(dataset_value: str) -> SnapshotRefreshProgress:
        """回當前 refresh 進度;無進行中 refresh(key 不存在)回 active=False。

        只讀 Redis、不觸 db → staticmethod,供聚合進度端點免建 db-bound service。
        """
        cached = await cache.cache_get(SnapshotService._progress_key(dataset_value))
        if cached is None:
            return SnapshotRefreshProgress(active=False)
        return SnapshotRefreshProgress.model_validate_json(cached)

    async def _collect_from_rds(self, dataset_value: str) -> list[_CollectedTable]:
        """同一連線內:內省全 schema 全表(唯讀)+ 逐表查 DS 字典 GAT_FILE 業務名(唯讀)。"""
        engine = introspect.get_engine(dataset_value)

        async def on_probe(done: int, total: int) -> None:
            await self._report_progress(dataset_value, "introspect", done, total)

        async with engine.connect() as conn:
            tables = await introspect.snapshot_tables(conn, on_progress=on_probe)
            await self._report_progress(dataset_value, "dictionary", len(tables), len(tables))
            # 批量查全部表名的字典業務名 + 模組代碼(各一次 RDS 來回,取代逐表 N 次)
            names = [str(t["name"]) for t in tables]
            comments = await fetch_table_comments(conn, names)
            modules = await fetch_table_modules(conn, names)
            collected: list[_CollectedTable] = [
                _CollectedTable(
                    schema_name=str(t["schema"]),
                    table_name=str(t["name"]),
                    business_name=comments.get(str(t["name"]).lower()),
                    module_code=modules.get(str(t["name"]).lower()),
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

    async def list_modules(self, dataset_value: str, schema: str) -> ModuleListResponse:
        """回指定 schema 下 distinct ERP 模組代碼(讀快照 + Redis cache;AD-115)。"""
        key = cache.cache_key("datasets", dataset_value, "modules", schema)
        cached = await cache.cache_get(key)
        if cached is not None:
            return ModuleListResponse.model_validate_json(cached)
        codes, has_unclassified = await self._repo.list_distinct_modules(
            Dataset(dataset_value), schema
        )
        response = ModuleListResponse(modules=codes, has_unclassified=has_unclassified)
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
            row_min=filters.row_min,
            row_max=filters.row_max,
            module=filters.module,
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

    async def list_summary(
        self, dataset_value: str, schema: str
    ) -> SchemaStatSummary:
        """回指定 schema 的資料總筆數分布概覽(讀快照 + Redis cache)。"""
        key = cache.cache_key("datasets", dataset_value, "summary", schema)
        cached = await cache.cache_get(key)
        if cached is not None:
            return SchemaStatSummary.model_validate_json(cached)
        total, nonempty, empty, capped = await self._repo.summary_by_schema(
            Dataset(dataset_value), schema
        )
        response = SchemaStatSummary(
            schema=schema,
            table_count=total,
            nonempty_count=nonempty,
            empty_count=empty,
            capped_count=capped,
        )
        await cache.cache_set(
            key, response.model_dump_json(by_alias=True), ttl_seconds=_CACHE_TTL_SECONDS
        )
        return response

    @staticmethod
    def _to_summary(row: RdsTableMeta) -> TableSummary:
        return TableSummary(
            name=row.table_name,
            business_name=row.business_name,
            module_code=row.module_code,
            column_count=row.column_count,
            row_count=row.row_count,
            snapshot_at=row.snapshot_at,
            last_synced_at=row.last_synced_at,
            last_transformed_at=row.last_transformed_at,
        )
