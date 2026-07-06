"""同步服務(SyncService):把逐表 / 全量同步 enqueue 至 taskiq(mirror_sync),回 run 資訊。

- 逐表:`sync_table(schema, table)`;全量:`sync_all()`(schema/table 皆空 → worker 端 DS 優先全量)。
- 就地執行 broker(pytest InMemoryBroker)已跑完 → 以結果 run_pid 換 run uid;佇列模式回 None。
- 全量為大規模 RDS 寫入,本層僅負責 enqueue;實際逐表鏡像 / 收尾由 worker mirror_sync 執行。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import AsyncTaskiqTask, InMemoryBroker

from app.repositories.run_repo import RunRepository
from app.schemas.sync import SyncTriggerResponse
from app.services.audit_service import AuditService
from app.worker.broker import broker
from app.worker.tasks import mirror_sync


class SyncService:
    def __init__(self, db: AsyncSession) -> None:
        self._run_repo = RunRepository(db)
        self._audit = AuditService(db)

    async def sync_table(
        self, schema: str, table: str, *, actor_uid: UUID
    ) -> SyncTriggerResponse:
        """enqueue 單表同步(mirror_sync 帶 schema/table)。"""
        task = await mirror_sync.kiq(schema=schema, table=table)
        run_uid = await self._resolve_run_uid(task)
        await self._audit.log(
            action="sync_trigger",
            actor_uid=actor_uid,
            target_type="etl_run",
            target_uid=run_uid,
            detail=f"觸發同步(單表 {schema}.{table},task_id={task.task_id})",
        )
        return SyncTriggerResponse(task_id=task.task_id, run_uid=run_uid, scope="table")

    async def sync_all(self, *, actor_uid: UUID) -> SyncTriggerResponse:
        """enqueue 全量同步(mirror_sync 不帶參數 → worker 取全來源表,DS 優先)。"""
        task = await mirror_sync.kiq()
        run_uid = await self._resolve_run_uid(task)
        await self._audit.log(
            action="sync_trigger",
            actor_uid=actor_uid,
            target_type="etl_run",
            target_uid=run_uid,
            detail=f"觸發同步(全量,DS 優先,task_id={task.task_id})",
        )
        return SyncTriggerResponse(task_id=task.task_id, run_uid=run_uid, scope="all")

    async def _resolve_run_uid(
        self, task: AsyncTaskiqTask[dict[str, object]]
    ) -> UUID | None:
        """就地執行 broker(InMemoryBroker)已跑完 → 以結果 run_pid 換 uid;佇列模式回 None。"""
        if not isinstance(broker, InMemoryBroker):
            return None
        result = await task.wait_result(timeout=5)
        if result.is_err:
            return None
        return_value: object = result.return_value
        if not isinstance(return_value, dict):
            return None
        run_pid = return_value.get("run_pid")
        if not isinstance(run_pid, int):
            return None
        run = await self._run_repo.find_by_pid(run_pid)
        return run.uid if run is not None else None
