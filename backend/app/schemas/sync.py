"""同步觸發 API 的請求 / 回應 schema(逐表 / 全量 → worker mirror_sync)。"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class SyncTableRequest(BaseModel):
    """單表同步請求:指定來源 schema 與表名(mirror 保留 schema.table 識別)。"""

    # 欄位名避開 BaseModel.schema;對外 JSON 仍用 "schema"(對齊 rawdata.SchemaSummary)
    schema_name: str = Field(
        alias="schema", min_length=1, max_length=128, description="來源 schema"
    )
    table: str = Field(min_length=1, max_length=200, description="來源表名")

    model_config = {"populate_by_name": True}


class SyncTriggerResponse(BaseModel):
    """同步觸發結果:taskiq 任務識別碼 + 新建 run uid(佇列模式下 enqueue 當下為 null)。"""

    task_id: str = Field(description="taskiq 任務識別碼")
    run_uid: UUID | None = Field(
        description=(
            "新建 run 的 uid;佇列模式(redis broker)下 run 由 worker 建立,"
            "enqueue 當下尚無 run → null(對齊 runs 觸發語意)"
        )
    )
    scope: str = Field(description="同步範圍:table(單表)/ all(全量)")
