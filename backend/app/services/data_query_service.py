"""資料列查詢服務(task-004,propose A3):對 RDS dataset 庫查指定表資料列,
key 依 confirmed semantic mapping 轉英文語意名。

安全面(`04-sql-safety.md`,本 task 核心):
- **schema 白名單**:僅限該 dataset 快照(rds_table_meta)已知 schema,未知即 404。
- **表 / 欄白名單**:表名須於副本 mapping(get_confirmed_map)命中且有 confirmed 欄位,
  否則 404;實際進 SQL 的欄名一律來自 confirmed 映射,再經 `quote_ident` 白名單引號化。
- **值走 bind params**:limit / offset 一律 bind,禁字串拼接。
- 404 訊息不回打原始輸入(schema / table),避免反射式資訊外洩。

不寫 RDS(唯讀 SELECT);副本 mapping 讀自有 DB(不即時打 RDS)。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.etl import introspect
from app.etl.comments import quote_ident
from app.models.rds_table_meta import Dataset
from app.models.semantic_mapping import SemanticMapping
from app.repositories.rds_table_meta_repo import RdsTableMetaRepository
from app.repositories.semantic_mapping_repo import SemanticMappingRepository
from app.schemas.data_query import DataColumnMeta, DataQueryResponse

# 404 統一訊息:不回打使用者輸入的 schema / table(避免反射),涵蓋
# 「schema 不在允許集合」與「表尚未複核 / 無 confirmed 欄位」兩種缺席情境。
_NOT_AVAILABLE_DETAIL = "指定資料表不存在或尚未複核"


class DataQueryService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._mapping_repo = SemanticMappingRepository(db)
        self._meta_repo = RdsTableMetaRepository(db)

    async def query_rows(
        self,
        *,
        dataset: str,
        schema_name: str,
        table_name: str,
        limit: int,
        offset: int,
    ) -> DataQueryResponse:
        """查指定表資料列,key 轉 confirmed 英文語意名(未 confirmed 欄不出現)。"""
        # 1) schema 白名單:限於該 dataset 快照已知 schema(未知不進 SQL)
        allowed = {
            schema for schema, _ in await self._meta_repo.list_schemas(Dataset(dataset))
        }
        if schema_name not in allowed:
            raise AppError(_NOT_AVAILABLE_DETAIL, response_code=404, status_code=404)

        # 2) 表 / 欄白名單:副本 mapping 命中的 confirmed 欄位才可進 SQL
        confirmed = await self._mapping_repo.get_confirmed_map(table_name)
        # column_name='' 為表層級英文名,非資料欄,過濾掉
        column_map = {col: eng for col, eng in confirmed.items() if col}
        if not column_map:
            raise AppError(_NOT_AVAILABLE_DETAIL, response_code=404, status_code=404)
        columns = sorted(column_map)  # 穩定順序(分頁 / 測試可重現)
        zh_names = await self._fetch_zh_names(table_name, columns)

        # 3) 對 RDS dataset 庫組查詢:識別字白名單引號化,值走 bind params
        raw_rows = await self._select_rows(
            dataset, schema_name, table_name, columns, limit=limit, offset=offset
        )

        # 4) key 轉英文語意名(僅含 confirmed 欄位)
        translated = [
            {column_map[col]: row.get(col) for col in columns} for row in raw_rows
        ]
        meta = [
            DataColumnMeta(english_name=column_map[col], zh_name=zh_names.get(col))
            for col in columns
        ]
        return DataQueryResponse(
            rows=translated, total_returned=len(translated), columns=meta
        )

    async def _fetch_zh_names(
        self, table_name: str, columns: list[str]
    ) -> dict[str, str | None]:
        """讀 confirmed 欄位的中文語意名(供 columns 元資訊;缺對應為 None)。"""
        if not columns:
            return {}
        stmt = select(SemanticMapping.column_name, SemanticMapping.zh_name).where(
            SemanticMapping.table_name == table_name,
            SemanticMapping.status == "confirmed",
            SemanticMapping.is_deleted.is_(False),
            SemanticMapping.column_name.in_(columns),
        )
        rows = (await self._db.execute(stmt)).all()
        return {str(col): (str(zh) if zh is not None else None) for col, zh in rows}

    async def _select_rows(
        self,
        dataset: str,
        schema_name: str,
        table_name: str,
        columns: list[str],
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        """對 RDS dataset 庫唯讀 SELECT confirmed 欄位:識別字白名單引號化,值 bind。"""
        select_list = ", ".join(quote_ident(col) for col in columns)
        qualified = f"{quote_ident(schema_name)}.{quote_ident(table_name)}"
        # ORDER BY 依 SELECT 欄位位置,確保 limit / offset 分頁穩定
        order_by = ", ".join(str(i) for i in range(1, len(columns) + 1))
        sql = text(
            f"SELECT {select_list} FROM {qualified}"
            f" ORDER BY {order_by} LIMIT :limit OFFSET :offset"
        )
        engine = introspect.get_engine(dataset)
        async with engine.connect() as conn:
            result = await conn.execute(sql.bindparams(limit=limit, offset=offset))
            return [dict(row) for row in result.mappings().all()]
