"""資料列查詢 API 回應 schema(task-004,propose A3)。

回傳 key 依 confirmed semantic mapping 轉為英文語意名;未 confirmed 欄位不出現
(不外流草稿名 / 魔術名)。`columns` 元資訊僅含語意名(english / zh),
不回傳原始 ERP 欄名(避免魔術名外流)。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DataColumnMeta(BaseModel):
    """單一 confirmed 欄位的語意元資訊(僅語意名,不含原始 ERP 欄名)。"""

    english_name: str = Field(description="英文語意名稱(回傳列的 key)")
    zh_name: str | None = Field(default=None, description="中文語意名稱(缺對應為 null)")


class DataQueryResponse(BaseModel):
    """指定表的資料列查詢結果:key 已轉英文語意名,僅含 confirmed 欄位。"""

    rows: list[dict[str, Any]] = Field(
        description="資料列;每列 key 為 english_name,僅含 confirmed 欄位"
    )
    total_returned: int = Field(description="本次回傳列數(<= limit)")
    columns: list[DataColumnMeta] = Field(
        description="本表 confirmed 欄位的語意元資訊(對應 rows 的 key)"
    )
