"""資料列查詢服務(task-004,propose A3):對 RDS dataset 庫查指定表資料列,
key 依 confirmed semantic mapping 轉英文語意名。

安全面(`04-sql-safety.md`,本 task 核心):
- **schema 白名單**:僅限該 dataset 快照(rds_table_meta)已知 schema,未知即 404。
- **表 / 欄白名單**:表名須於副本 mapping(get_confirmed_map)命中且有 confirmed 欄位,
  否則 404;實際進 SQL 的欄名一律來自 confirmed 映射,再經 `quote_ident` 白名單引號化。
- **confirmed ∩ 實際欄位**:進 SELECT 前先查該 (schema, table) 於 RDS dataset 庫的實際
  欄位集合,與 confirmed 欄位取交集才組 SQL,防 ERP 端欄位改名 / 移除導致 mapping 漂移時
  SELECT 直接拋 Postgres 例外(500);交集為空(含表已不存在)一律走既有 404。
- **值走 bind params**:limit / offset 一律 bind,禁字串拼接。
- 404 訊息不回打原始輸入(schema / table),避免反射式資訊外洩。

不寫 RDS(唯讀 SELECT);副本 mapping 讀自有 DB(不即時打 RDS)。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.exceptions import AppError
from app.etl import introspect
from app.etl.comments import quote_ident
from app.models.rds_table_meta import Dataset
from app.models.semantic_mapping import SemanticMapping
from app.repositories.rds_table_meta_repo import RdsTableMetaRepository
from app.repositories.semantic_mapping_repo import SemanticMappingRepository
from app.schemas.data_query import DataColumnMeta, DataQueryResponse

# 404 統一訊息:不回打使用者輸入的 schema / table(避免反射),涵蓋
# 「schema 不在允許集合」「表尚未複核 / 無 confirmed 欄位」「confirmed 欄位與實際欄位
# 交集為空(含表已不存在)」三種缺席情境(AD-111)。
_NOT_AVAILABLE_DETAIL = "指定資料表不存在或尚未複核"

# 實際欄位集合查詢:identifier 走 bind params(非拼接),供 confirmed ∩ 實際欄位比對
_ACTUAL_COLUMNS_SQL = text(
    """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = :schema AND table_name = :table
    """
)


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

        # 3) confirmed ∩ 實際欄位後組查詢:識別字白名單引號化,值走 bind params;
        #    交集為空(含表不存在)→ columns 回空,走既有 404(AD-111)
        columns, raw_rows = await self._select_rows(
            dataset, schema_name, table_name, sorted(column_map), limit=limit, offset=offset
        )
        if not columns:
            raise AppError(_NOT_AVAILABLE_DETAIL, response_code=404, status_code=404)
        zh_names = await self._fetch_zh_names(table_name, columns)

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
        candidate_columns: list[str],
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """對 RDS dataset 庫唯讀 SELECT:先查該表實際欄位集合,與 `candidate_columns`
        取交集後才組 SQL(AD-111:防 confirmed mapping 與實體 schema 漂移直接拋例外);
        識別字白名單引號化,值走 bind params。交集為空(含表不存在)回 `([], [])`。
        """
        engine = introspect.get_engine(dataset)
        async with engine.connect() as conn:
            actual = await self._fetch_actual_columns(conn, schema_name, table_name)
            columns = sorted(set(candidate_columns) & actual)
            if not columns:
                return [], []
            select_list = ", ".join(quote_ident(col) for col in columns)
            qualified = f"{quote_ident(schema_name)}.{quote_ident(table_name)}"
            # ORDER BY 改依 SELECT 首欄(單一穩定鍵),取代全欄排序(AD-114:降低排序成本)
            sql = text(
                f"SELECT {select_list} FROM {qualified}"
                " ORDER BY 1 LIMIT :limit OFFSET :offset"
            )
            result = await conn.execute(sql.bindparams(limit=limit, offset=offset))
            rows = [dict(row) for row in result.mappings().all()]
        return columns, rows

    @staticmethod
    async def _fetch_actual_columns(
        conn: AsyncConnection, schema_name: str, table_name: str
    ) -> set[str]:
        """查該 (schema, table) 於 RDS dataset 庫的實際欄位集合(identifier 走 bind params)。

        表不存在時回空集合(交由呼叫端與 candidate 交集後自然得空,不特判)。
        """
        result = await conn.execute(
            _ACTUAL_COLUMNS_SQL, {"schema": schema_name, "table": table_name}
        )
        return {str(row[0]) for row in result.all()}
