"""全局進度聚合 API 的回應 schema(AD-121):四種進度一次回,前端 layout 單一輪詢。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.rawdata import SnapshotRefreshProgress
from app.schemas.run import ActiveRunResponse


class GlobalProgressResponse(BaseModel):
    sync: ActiveRunResponse | None = Field(
        description="執行中 run 進度(同 GET /runs/active;無進行中 run 為 null)"
    )
    snapshot_source: SnapshotRefreshProgress = Field(
        description="source 快照 refresh 進度(無進行中 active=false)"
    )
    snapshot_target: SnapshotRefreshProgress = Field(
        description="target 快照 refresh 進度(無進行中 active=false)"
    )
    apply: SnapshotRefreshProgress = Field(
        description="語意映射套用變更進度(無進行中 active=false)"
    )
