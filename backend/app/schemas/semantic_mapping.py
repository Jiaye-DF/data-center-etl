"""語意映射管理 API 的請求 / 回應 schema(v1.5.1 task-004)。

資料來源為目標 RDS `erp_metadata.semantic_mappings`(唯一事實來源);
`column_name = ''` 代表表層級映射(決定 view 名),前端顯示為「(表層級)」。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# 英文名白名單:小寫開頭,僅小寫英數與底線(view / JSON key 皆可安全使用)
ENGLISH_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"

MappingStatus = Literal["draft", "confirmed"]


class SemanticMappingItem(BaseModel):
    table_name: str = Field(description="ERP 表名(如 BMA_FILE)")
    column_name: str = Field(description="欄名;空字串代表表層級映射(view 名依據)")
    english_name: str = Field(description="英文語意名")
    zh_name: str | None = Field(default=None, description="中文名(字典語意;可為 null)")
    status: MappingStatus = Field(description="審核狀態:draft / confirmed")
    updated_by: str | None = Field(default=None, description="最後異動者(系統/使用者識別)")
    updated_at: datetime = Field(description="最後異動時間(naive UTC+8)")


class SemanticMappingListResponse(BaseModel):
    items: list[SemanticMappingItem]
    total: int = Field(description="符合條件總筆數(分頁分母)")
    page: int
    page_size: int


class SemanticTableSummary(BaseModel):
    table_name: str
    draft_count: int = Field(description="該表 draft 筆數")
    confirmed_count: int = Field(description="該表 confirmed 筆數")
    zh_name: str | None = Field(default=None, description="表層級中文名(無表層級列為 null)")
    english_name: str | None = Field(
        default=None, description="表層級英文語意名(無表層級列為 null)"
    )


class SemanticTableListResponse(BaseModel):
    items: list[SemanticTableSummary]


class SemanticMappingUpdateRequest(BaseModel):
    """單列更新:以複合鍵定位;僅帶入的欄位會被更新(至少一項)。"""

    table_name: str = Field(min_length=1, max_length=128)
    column_name: str = Field(default="", max_length=128, description="空字串=表層級映射")
    english_name: str | None = Field(
        default=None,
        max_length=128,
        pattern=ENGLISH_NAME_PATTERN,
        description="英文語意名(小寫開頭,僅小寫英數與底線)",
    )
    zh_name: str | None = Field(default=None, max_length=256)
    status: MappingStatus | None = Field(default=None)


class SemanticConfirmTableRequest(BaseModel):
    table_name: str = Field(min_length=1, max_length=128)


class SemanticAffectedResponse(BaseModel):
    affected: int = Field(description="受影響列數")


class SemanticSyncViewsQueuedResponse(BaseModel):
    """「套用變更」派工受理結果(AD-122:實際執行移至 worker,統計見 worker log)。"""

    queued: bool = Field(description="是否已派工 worker 執行(進度輪詢聚合進度端點)")
