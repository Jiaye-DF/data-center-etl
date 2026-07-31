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
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.exceptions import AppError
from app.etl import introspect
from app.etl.comments import quote_ident
from app.etl.semantic_schema import SEMANTIC_SCHEMA, SEMANTIC_TABLE
from app.models.client_setting import CLIENT_SETTING_SCHEMA
from app.schemas.semantic_mapping import (
    SemanticAffectedResponse,
    SemanticMappingItem,
    SemanticMappingListResponse,
    SemanticMappingUpdateRequest,
    SemanticTableListResponse,
    SemanticTableSummary,
)

_QUALIFIED = f"{quote_ident(SEMANTIC_SCHEMA)}.{quote_ident(SEMANTIC_TABLE)}"
_CLIENT_SETTING = quote_ident(CLIENT_SETTING_SCHEMA)

# column_name = '' 代表表層級映射(該列的 english_name 即整張表的英文名)
_TABLE_LEVEL = ""

_MAPPING_NOT_FOUND = "映射不存在"
_TABLE_ENGLISH_CONFLICT = "表層級英文名已被其他表使用,請改用其他名稱"
_COLUMN_ENGLISH_CONFLICT = "同一張表內已有欄位使用此英文名,請改用其他名稱"
# 授權以英文名純字串儲存且無 FK(AD-154);改名會靜默作廢或錯接既有授權,故一律擋下
_ENGLISH_NAME_REFERENCED = "該英文名已被權限設定引用,請先解除相關授權"

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

# ── english_name 改名防護(v1.6.1 fixed AD-154 + AD-150)────────────────
_CURRENT_ROW_SQL = text(
    f"SELECT english_name, status FROM {_QUALIFIED}"
    " WHERE table_name = :t AND column_name = :c"
)

_TABLE_ENGLISH_NAME_SQL = text(
    f"SELECT english_name FROM {_QUALIFIED} WHERE table_name = :t AND column_name = ''"
)

# 表層級英文名全域唯一(對齊 semantic_schema 的 partial unique index)
_DUPLICATE_TABLE_ENGLISH_SQL = text(
    f"SELECT 1 FROM {_QUALIFIED}"
    " WHERE column_name = '' AND english_name = :e AND table_name <> :t LIMIT 1"
)

# 欄位英文名於同一張表內唯一(跨表同名合法,對外 key 是 表.欄位)
_DUPLICATE_COLUMN_ENGLISH_SQL = text(
    f"SELECT 1 FROM {_QUALIFIED}"
    " WHERE table_name = :t AND column_name <> '' AND column_name <> :c"
    " AND english_name = :e LIMIT 1"
)

# 新環境可能尚未建 client_setting schema → 先探再查,避免既有端點被 UndefinedTable 打掛
_CLIENT_SETTING_READY_SQL = text(
    f"SELECT to_regclass('{CLIENT_SETTING_SCHEMA}.operation_items')"
)

_REFERENCED_TABLE_SQL = text(
    f"""
    SELECT 1 FROM {_CLIENT_SETTING}.operation_items
     WHERE is_deleted = false AND table_name = :name
    UNION ALL
    SELECT 1 FROM {_CLIENT_SETTING}.profile_items
     WHERE is_deleted = false AND table_name = :name
    UNION ALL
    SELECT 1 FROM {_CLIENT_SETTING}.exception_items
     WHERE is_deleted = false AND table_name = :name
    LIMIT 1
    """
)

_REFERENCED_COLUMN_SQL = text(
    f"""
    SELECT 1 FROM {_CLIENT_SETTING}.operation_items
     WHERE is_deleted = false AND table_name = :t AND column_name = :c
    UNION ALL
    SELECT 1 FROM {_CLIENT_SETTING}.profile_items
     WHERE is_deleted = false AND table_name = :t AND column_name = :c
    UNION ALL
    SELECT 1 FROM {_CLIENT_SETTING}.exception_items
     WHERE is_deleted = false AND table_name = :t AND column_name = :c
    LIMIT 1
    """
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
            if payload.english_name is not None:
                await self._guard_english_rename(conn, payload)
            row = (await conn.execute(update_sql, params)).mappings().first()
        if row is None:
            raise AppError(_MAPPING_NOT_FOUND, response_code=404, status_code=404)
        return SemanticMappingItem.model_validate(dict(row))

    async def _guard_english_rename(
        self, conn: AsyncConnection, payload: SemanticMappingUpdateRequest
    ) -> None:
        """english_name 改名前的兩道關卡(v1.6.1 fixed AD-154 + AD-150)。

        1. **查重**:表層級英文名全域唯一、欄位英文名同表唯一(DB 端 partial unique 只兜
           表層級,且是 409 語意;此處先擋以給出可讀訊息)。
        2. **下游引用**:`client_setting` 的授權項以英文名純字串儲存、與本表無 FK —— 改名
           會靜默作廢(指向不存在的名字)或錯接(改成另一張表的原名),故 confirmed 列一旦
           被引用即擋下,要求先解除授權再改名。
        """
        new_name = payload.english_name
        if new_name is None:
            return
        current = (
            await conn.execute(
                _CURRENT_ROW_SQL, {"t": payload.table_name, "c": payload.column_name}
            )
        ).first()
        if current is None:
            raise AppError(_MAPPING_NOT_FOUND, response_code=404, status_code=404)
        old_name, status = str(current[0]), str(current[1])
        if new_name == old_name:
            return

        is_table_level = payload.column_name == _TABLE_LEVEL
        if is_table_level:
            duplicated = (
                await conn.execute(
                    _DUPLICATE_TABLE_ENGLISH_SQL,
                    {"e": new_name, "t": payload.table_name},
                )
            ).first()
            conflict = _TABLE_ENGLISH_CONFLICT
        else:
            duplicated = (
                await conn.execute(
                    _DUPLICATE_COLUMN_ENGLISH_SQL,
                    {"t": payload.table_name, "c": payload.column_name, "e": new_name},
                )
            ).first()
            conflict = _COLUMN_ENGLISH_CONFLICT
        if duplicated is not None:
            raise AppError(conflict, response_code=409, status_code=409)

        # draft 列不可能被授權引用(授權只認 confirmed 映射)→ 無須反查
        if status != "confirmed":
            return
        if (await conn.execute(_CLIENT_SETTING_READY_SQL)).scalar() is None:
            return
        if is_table_level:
            referenced = (
                await conn.execute(_REFERENCED_TABLE_SQL, {"name": old_name})
            ).first()
        else:
            table_english = (
                await conn.execute(_TABLE_ENGLISH_NAME_SQL, {"t": payload.table_name})
            ).scalar()
            if table_english is None:
                return
            referenced = (
                await conn.execute(
                    _REFERENCED_COLUMN_SQL, {"t": str(table_english), "c": old_name}
                )
            ).first()
        if referenced is not None:
            raise AppError(_ENGLISH_NAME_REFERENCED, response_code=409, status_code=409)

    async def confirm_table(
        self, table_name: str, actor_uid: UUID
    ) -> SemanticAffectedResponse:
        async with self._engine.begin() as conn:
            result = await conn.execute(
                _CONFIRM_TABLE_SQL, {"t": table_name, "actor": actor_uid}
            )
        affected = int(result.rowcount or 0)
        return SemanticAffectedResponse(affected=affected)
