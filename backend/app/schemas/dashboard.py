"""總覽儀表板聚合回應 schema:同步健康 / 待處理失敗表 / 排程概況 / 資料規模。

單一 GET /dashboard/overview 一次撈回,避免前端打多支 query。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DashboardLatestRun(BaseModel):
    uid: UUID = Field(description="最新一筆 run 的公開識別碼")
    trigger_type: str = Field(description="觸發類型(schedule / manual)")
    status: str = Field(description="狀態(pending / running / success / failed)")
    total_tables: int = Field(description="該 run 涵蓋表數")
    success_tables: int = Field(description="成功表數")
    failed_tables: int = Field(description="失敗表數")
    finished_at: datetime | None = Field(description="結束時間(尚未結束為 null)")


class DashboardSyncHealth(BaseModel):
    latest_run: DashboardLatestRun | None = Field(description="最新一筆 run(無則 null)")
    recent_total: int = Field(description="最近 N 筆 run 總數")
    recent_success: int = Field(description="最近 N 筆中成功數")
    recent_failed: int = Field(description="最近 N 筆中失敗數")


class DashboardFailedTable(BaseModel):
    source_schema: str = Field(description="來源 schema")
    source_table: str = Field(description="來源表")
    error_message: str | None = Field(description="錯誤訊息(機密已遮罩;無則 null)")


class DashboardPendingFailures(BaseModel):
    run_uid: UUID | None = Field(
        description="失敗表所屬 run(最新 run 有失敗時才有值,可點進 log)"
    )
    items: list[DashboardFailedTable] = Field(description="最新一輪失敗表清單(封頂)")


class DashboardSchedules(BaseModel):
    enabled_count: int = Field(description="啟用中來源表排程數")
    table_total: int = Field(description="來源表總數")
    enabled_cron_exprs: list[str] = Field(
        description="啟用中排程的相異 cron(供前端算最近一班執行時間)"
    )


class DashboardDatasetScale(BaseModel):
    dataset: str = Field(description="資料集(source / target)")
    table_count: int = Field(description="總表數")
    nonempty_count: int = Field(description="有資料表數(row_count>0)")
    empty_count: int = Field(description="空表數(row_count=0)")
    last_snapshot_at: datetime | None = Field(description="最近快照重建時間(無則 null)")
    last_synced_at: datetime | None = Field(description="最近同步時間(無則 null)")


class DashboardOverview(BaseModel):
    sync_health: DashboardSyncHealth = Field(description="同步健康")
    pending_failures: DashboardPendingFailures = Field(description="待處理失敗表")
    schedules: DashboardSchedules = Field(description="排程概況")
    datasets: list[DashboardDatasetScale] = Field(
        description="資料規模 + 快照新鮮度(source / target)"
    )
