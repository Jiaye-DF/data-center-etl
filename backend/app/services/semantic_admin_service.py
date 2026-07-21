"""語意映射管理服務(v1.5.1 task-004):直接讀寫目標 RDS `erp_metadata.semantic_mappings`。

- RDS 為唯一事實來源(propose v1.5.0 A5,禁雙向同步)→ 編輯**不**寫自有 DB 副本;
  副本仍由同步收尾整表重灌跟上,故編輯後的即時生效交由「同步 view」觸發(task-005)。
- 連線重用 `introspect.get_engine("target")` 的程序內快取 engine(連線池共用)。
- SQL 值一律 bind params;識別字為白名單常值(`04-sql-safety.md`)。
- `updated_at` 為 naive UTC+8(datetime2 等價通則):RDS 系統時鐘為 UTC,
  寫入以 `now() AT TIME ZONE 'Asia/Taipei'` 轉出本地值(對齊 semantic_schema.py)。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text

from app.core.exceptions import AppError
from app.etl import introspect
from app.etl.comments import quote_ident
from app.etl.semantic_schema import SEMANTIC_SCHEMA, SEMANTIC_TABLE
from app.schemas.semantic_mapping import (
    SemanticAffectedResponse,
    SemanticMappingItem,
    SemanticMappingListResponse,
    SemanticMappingUpdateRequest,
    SemanticTableListResponse,
    SemanticTableSummary,
)

_QUALIFIED = f"{quote_ident(SEMANTIC_SCHEMA)}.{quote_ident(SEMANTIC_TABLE)}"

# updated_by 於 RDS 為 uuid(v1.5.1 fixed #3),API schema 對外為字串 → SELECT 即轉 text
_SELECT_COLUMNS = (
    "table_name, column_name, english_name, zh_name, status,"
    " CAST(updated_by AS text) AS updated_by, updated_at"
)

# 表層級列(column_name='')的中英文名一併帶出,供前端表名 combobox 中英搜尋
_TABLES_SQL = text(
    f"""
    SELECT table_name,
           count(*) FILTER (WHERE status = 'draft') AS draft_count,
           count(*) FILTER (WHERE status = 'confirmed') AS confirmed_count,
           max(zh_name) FILTER (WHERE column_name = '') AS zh_name,
           max(english_name) FILTER (WHERE column_name = '') AS english_name
    FROM {_QUALIFIED}
    GROUP BY table_name
    ORDER BY table_name
    """
)

_CONFIRM_TABLE_SQL = text(
    f"UPDATE {_QUALIFIED} SET status = 'confirmed', updated_by = :actor,"
    " updated_at = (now() AT TIME ZONE 'Asia/Taipei')"
    " WHERE table_name = :t AND status <> 'confirmed'"
)


class SemanticAdminService:
    """語意映射管理:列表 / 篩選 / 單列更新 / 整表轉態(全 admin-only,由路由層把關)。"""

    def __init__(self) -> None:
        self._engine = introspect.get_engine("target")

    # ── 讀取 ────────────────────────────────────────────────────────────
    async def list_mappings(
        self,
        *,
        table: str = "",
        status: str = "all",
        keyword: str = "",
        page: int = 1,
        page_size: int = 50,
    ) -> SemanticMappingListResponse:
        conds: list[str] = []
        params: dict[str, object] = {}
        if table != "":
            conds.append("table_name = :table")
            params["table"] = table
        if status in ("draft", "confirmed"):
            conds.append("status = :status")
            params["status"] = status
        if keyword != "":
            # 中英皆可:表名 / 欄名 / 英文語意名 / 中文名 子字串(供 combobox 搜尋)
            conds.append(
                "(table_name ILIKE :kw OR column_name ILIKE :kw"
                " OR english_name ILIKE :kw OR zh_name ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
        where = f" WHERE {' AND '.join(conds)}" if conds else ""
        offset = (page - 1) * page_size

        async with self._engine.connect() as conn:
            total = (
                await conn.execute(
                    text(f"SELECT count(*) FROM {_QUALIFIED}{where}"), params
                )
            ).scalar_one()
            rows = (
                await conn.execute(
                    text(
                        f"SELECT {_SELECT_COLUMNS} FROM {_QUALIFIED}{where}"
                        " ORDER BY table_name, column_name LIMIT :limit OFFSET :offset"
                    ),
                    {**params, "limit": page_size, "offset": offset},
                )
            ).mappings().all()
        return SemanticMappingListResponse(
            items=[SemanticMappingItem.model_validate(dict(r)) for r in rows],
            total=int(total),
            page=page,
            page_size=page_size,
        )

    async def list_tables(self) -> SemanticTableListResponse:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(_TABLES_SQL)).mappings().all()
        return SemanticTableListResponse(
            items=[SemanticTableSummary.model_validate(dict(r)) for r in rows]
        )

    # ── 寫入(bind params;逐列 / 整表)───────────────────────────────────
    async def update_mapping(
        self, payload: SemanticMappingUpdateRequest, actor_uid: UUID
    ) -> SemanticMappingItem:
        sets: list[str] = []
        # actor 綁 UUID 物件(欄位為 uuid 型別,v1.5.1 fixed #3)
        params: dict[str, object] = {
            "t": payload.table_name,
            "c": payload.column_name,
            "actor": actor_uid,
        }
        fields_set = payload.model_fields_set
        if payload.english_name is not None:
            sets.append("english_name = :e")
            params["e"] = payload.english_name
        # zh_name 允許顯式清空(帶 null);未帶入則不動
        if "zh_name" in fields_set:
            sets.append("zh_name = :z")
            params["z"] = payload.zh_name
        if payload.status is not None:
            sets.append("status = :s")
            params["s"] = payload.status
        if not sets:
            raise AppError("未提供任何可更新欄位", response_code=422, status_code=422)
        sets.append("updated_by = :actor")
        sets.append("updated_at = (now() AT TIME ZONE 'Asia/Taipei')")

        update_sql = text(
            f"UPDATE {_QUALIFIED} SET {', '.join(sets)}"
            " WHERE table_name = :t AND column_name = :c"
            f" RETURNING {_SELECT_COLUMNS}"
        )
        async with self._engine.begin() as conn:
            row = (await conn.execute(update_sql, params)).mappings().first()
        if row is None:
            raise AppError("映射不存在", response_code=404, status_code=404)
        return SemanticMappingItem.model_validate(dict(row))

    async def confirm_table(
        self, table_name: str, actor_uid: UUID
    ) -> SemanticAffectedResponse:
        async with self._engine.begin() as conn:
            result = await conn.execute(
                _CONFIRM_TABLE_SQL, {"t": table_name, "actor": actor_uid}
            )
        affected = int(result.rowcount or 0)
        return SemanticAffectedResponse(affected=affected)
