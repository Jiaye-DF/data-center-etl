from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models import EtlRunLog, EtlTable
from app.repositories.etl_config_repo import EtlConfigRepository
from app.schemas.etl_config import (
    EtlMappingResponse,
    EtlMappingUpsertRequest,
    EtlTableCreateRequest,
    EtlTableDetailResponse,
    EtlTableListResponse,
    EtlTableSummaryResponse,
    EtlTableUpdateRequest,
)
from app.services.audit_service import AuditService

# 合法轉換型別(對齊 app/etl/transforms.py _CONVERTERS;NULL 為不轉換)
_VALID_TRANSFORM_TYPES = frozenset({"str", "int", "float"})


class EtlConfigService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = EtlConfigRepository(db)
        self._audit = AuditService(db)

    # ── 查詢 ────────────────────────────────────────────────────────────
    async def list_tables(self, *, page: int, page_size: int) -> EtlTableListResponse:
        offset = (page - 1) * page_size
        tables, total = await self._repo.list_tables(offset=offset, limit=page_size)
        pids = [t.pid for t in tables]
        counts = await self._repo.mapping_count_by_table_pid(pids)
        latest_logs = await self._repo.latest_run_log_by_table_pid(pids)
        items = [
            self._to_summary(t, counts.get(t.pid, 0), latest_logs.get(t.pid)) for t in tables
        ]
        return EtlTableListResponse(items=items, total=total, page=page, page_size=page_size)

    async def get_table_detail(self, uid: UUID) -> EtlTableDetailResponse:
        table = await self._get_table_or_404(uid)
        return await self._to_detail(table)

    # ── 寫入 ────────────────────────────────────────────────────────────
    async def create_table(
        self, payload: EtlTableCreateRequest, actor_uid: UUID
    ) -> EtlTableDetailResponse:
        mappings = self._validate_mappings(payload.mappings)
        existing = await self._repo.find_table_by_source(
            payload.source_schema, payload.source_table
        )
        if existing is not None:
            raise AppError(
                "來源表已納管(source_schema + source_table 重複)",
                response_code=409,
                status_code=409,
            )
        table = await self._repo.create_table(
            source_schema=payload.source_schema,
            source_table=payload.source_table,
            target_schema=payload.target_schema,
            target_table=payload.target_table,
            description=payload.description,
            is_enabled=payload.is_enabled,
            actor_uid=actor_uid,
        )
        for item in mappings:
            await self._repo.create_mapping(
                etl_table_pid=table.pid,
                source_column=item.source_column,
                target_column=item.target_column,
                transform_type=item.transform_type,
                comment=item.comment or "",
                sort_order=item.sort_order,
                actor_uid=actor_uid,
            )
        await self._audit.log(
            action="etl_table_create",
            actor_uid=actor_uid,
            target_type="etl_table",
            target_uid=table.uid,
            detail=(
                f"新增 ETL 表 {table.source_schema}.{table.source_table} → "
                f"{table.target_schema}.{table.target_table}(mappings {len(mappings)} 欄)"
            ),
        )
        return await self._to_detail(table)

    async def update_table(
        self, uid: UUID, payload: EtlTableUpdateRequest, actor_uid: UUID
    ) -> EtlTableDetailResponse:
        table = await self._get_table_or_404(uid)
        fields_set = payload.model_fields_set
        if "target_schema" in fields_set and payload.target_schema is not None:
            table.target_schema = payload.target_schema
        if "target_table" in fields_set and payload.target_table is not None:
            table.target_table = payload.target_table
        if "description" in fields_set:
            table.description = payload.description
        await self._repo.touch_table(table, actor_uid)
        await self._audit.log(
            action="etl_table_update",
            actor_uid=actor_uid,
            target_type="etl_table",
            target_uid=table.uid,
            detail=(
                f"更新 ETL 表 {table.source_schema}.{table.source_table}"
                f"(欄位:{', '.join(sorted(fields_set)) or '無'})"
            ),
        )
        return await self._to_detail(table)

    async def delete_table(self, uid: UUID, actor_uid: UUID) -> None:
        table = await self._get_table_or_404(uid)
        # 軟刪除表設定時一併軟刪其 mappings(禁物理刪除)
        await self._repo.soft_delete_mappings_by_table_pid(table.pid, actor_uid)
        await self._repo.soft_delete_table(table, actor_uid)
        await self._audit.log(
            action="etl_table_delete",
            actor_uid=actor_uid,
            target_type="etl_table",
            target_uid=table.uid,
            detail=f"刪除(軟刪除)ETL 表 {table.source_schema}.{table.source_table}",
        )

    async def set_enabled(
        self, uid: UUID, *, enabled: bool, actor_uid: UUID
    ) -> EtlTableDetailResponse:
        table = await self._get_table_or_404(uid)
        table.is_enabled = enabled
        await self._repo.touch_table(table, actor_uid)
        await self._audit.log(
            action="etl_table_enable" if enabled else "etl_table_disable",
            actor_uid=actor_uid,
            target_type="etl_table",
            target_uid=table.uid,
            detail=(
                f"{'啟用' if enabled else '停用'} ETL 表 "
                f"{table.source_schema}.{table.source_table}"
            ),
        )
        return await self._to_detail(table)

    async def replace_mappings(
        self, uid: UUID, mappings: list[EtlMappingUpsertRequest], actor_uid: UUID
    ) -> EtlTableDetailResponse:
        validated = self._validate_mappings(mappings)
        table = await self._get_table_or_404(uid)
        # 全量替換:舊 mappings 軟刪除後重建(禁物理刪除)
        await self._repo.soft_delete_mappings_by_table_pid(table.pid, actor_uid)
        for item in validated:
            await self._repo.create_mapping(
                etl_table_pid=table.pid,
                source_column=item.source_column,
                target_column=item.target_column,
                transform_type=item.transform_type,
                comment=item.comment or "",
                sort_order=item.sort_order,
                actor_uid=actor_uid,
            )
        await self._repo.touch_table(table, actor_uid)
        await self._audit.log(
            action="mappings_replace",
            actor_uid=actor_uid,
            target_type="etl_table",
            target_uid=table.uid,
            detail=(
                f"全量替換 ETL 表 {table.source_schema}.{table.source_table} "
                f"的 mappings({len(validated)} 欄)"
            ),
        )
        return await self._to_detail(table)

    # ── 內部 ────────────────────────────────────────────────────────────
    async def _get_table_or_404(self, uid: UUID) -> EtlTable:
        table = await self._repo.find_table_by_uid(uid)
        if table is None:
            raise AppError("ETL 表設定不存在", response_code=404, status_code=404)
        return table

    def _validate_mappings(
        self, mappings: list[EtlMappingUpsertRequest]
    ) -> list[EtlMappingUpsertRequest]:
        """驗證 mapping 商業規則:每個目標欄位必有 comment(缺值 400,不可靜默通過)。"""
        seen_targets: set[str] = set()
        normalized: list[EtlMappingUpsertRequest] = []
        for item in mappings:
            comment = (item.comment or "").strip()
            if not comment:
                raise AppError(
                    f"目標欄位 {item.target_column} 缺少 comment(每欄位必帶 Comment)",
                    response_code=400,
                    status_code=400,
                )
            if item.transform_type is not None and (
                item.transform_type not in _VALID_TRANSFORM_TYPES
            ):
                raise AppError(
                    f"目標欄位 {item.target_column} 的 transform_type 不合法"
                    "(僅允許 str / int / float 或不填)",
                    response_code=400,
                    status_code=400,
                )
            if item.target_column in seen_targets:
                raise AppError(
                    f"目標欄位 {item.target_column} 重複",
                    response_code=400,
                    status_code=400,
                )
            seen_targets.add(item.target_column)
            normalized.append(item.model_copy(update={"comment": comment}))
        return normalized

    def _to_summary(
        self, table: EtlTable, mapping_count: int, latest_log: EtlRunLog | None
    ) -> EtlTableSummaryResponse:
        return EtlTableSummaryResponse(
            uid=table.uid,
            source_schema=table.source_schema,
            source_table=table.source_table,
            target_schema=table.target_schema,
            target_table=table.target_table,
            is_enabled=table.is_enabled,
            description=table.description,
            mapping_count=mapping_count,
            last_run_status=latest_log.status if latest_log is not None else None,
            last_run_at=(
                latest_log.finished_at or latest_log.started_at
                if latest_log is not None
                else None
            ),
        )

    async def _to_detail(self, table: EtlTable) -> EtlTableDetailResponse:
        mappings = await self._repo.list_mappings_by_table_pid(table.pid)
        latest_logs = await self._repo.latest_run_log_by_table_pid([table.pid])
        summary = self._to_summary(table, len(mappings), latest_logs.get(table.pid))
        return EtlTableDetailResponse(
            **summary.model_dump(),
            mappings=[EtlMappingResponse.model_validate(m) for m in mappings],
        )
