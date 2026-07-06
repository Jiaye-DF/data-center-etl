"""worker task:`run_etl` — 排程 / 手動觸發的 ETL 執行入口。

worker 啟動指令(供 task-012 容器 command 使用):

    uv run taskiq worker app.worker.tasks:broker

流程:建立 `etl_runs` 紀錄(engine 內 store.create_run)→ 執行逐表管線 →
任何引擎外例外都把 run 補標 failed + log 錯誤明細,不留 running 殭屍狀態。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import asdict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.core.logging import setup_logging
from app.etl.engine import (
    DbRunStore,
    EtlTableConfig,
    RunStore,
    SourceReader,
    TargetWriter,
    load_table_configs,
    mask_secrets,
)
from app.etl.engine import run_etl as run_etl_pipeline
from app.etl.reader import PostgresSourceReader
from app.etl.writer import PostgresTargetWriter
from app.worker.broker import broker

# worker / scheduler 入口(taskiq 以本模組啟動):未組態時 root logger 預設 WARNING,
# engine 的逐表 info log 會被靜音(scan R-LOG-005)
setup_logging()

logger = logging.getLogger(__name__)

# worker 為系統動作,無登入使用者 → 全零 UUID 代表系統帳號(同 seed_etl_config 約定)
SYSTEM_ACTOR_UID = UUID("00000000-0000-0000-0000-000000000000")


class RunStateTracker:
    """包裝 RunStore:追蹤 run 是否已建立 / 收尾,供引擎外例外時補標 failed。"""

    def __init__(self, inner: RunStore) -> None:
        self._inner = inner
        self.created_run_pid: int | None = None
        self.run_finished = False

    async def create_run(self, *, trigger_type: str, schedule_pid: int | None) -> int:
        run_pid = await self._inner.create_run(
            trigger_type=trigger_type, schedule_pid=schedule_pid
        )
        self.created_run_pid = run_pid
        return run_pid

    async def start_table_log(self, *, run_pid: int, config: EtlTableConfig) -> int:
        return await self._inner.start_table_log(run_pid=run_pid, config=config)

    async def finish_table_log(
        self,
        log_pid: int,
        *,
        status: str,
        row_count: int | None,
        duration_ms: int | None,
        error_message: str | None,
        error_stack: str | None,
    ) -> None:
        await self._inner.finish_table_log(
            log_pid,
            status=status,
            row_count=row_count,
            duration_ms=duration_ms,
            error_message=error_message,
            error_stack=error_stack,
        )

    async def add_skipped_log(self, *, run_pid: int, config: EtlTableConfig) -> None:
        await self._inner.add_skipped_log(run_pid=run_pid, config=config)

    async def finish_run(
        self,
        run_pid: int,
        *,
        status: str,
        total_tables: int,
        success_tables: int,
        failed_tables: int,
        error_message: str | None,
    ) -> None:
        await self._inner.finish_run(
            run_pid,
            status=status,
            total_tables=total_tables,
            success_tables=success_tables,
            failed_tables=failed_tables,
            error_message=error_message,
        )
        self.run_finished = True


# 以下 factory 於呼叫時動態查 module 屬性 → 測試可 monkeypatch 注入 fake(不連真 DB / RDS)


def make_store(session: AsyncSession) -> RunStore:
    """建立 production RunStore(DbRunStore,系統帳號)。"""
    return DbRunStore(session, actor_uid=SYSTEM_ACTOR_UID)


def make_reader() -> SourceReader:
    """建立來源讀取器(AWS_RDS_* + AWS_RDS_SOURCE_DB env,lazy 連線)。"""
    return PostgresSourceReader()


def make_writer() -> TargetWriter:
    """建立目標寫入器(AWS_RDS_* + AWS_RDS_TARGET_DB env,lazy 連線)。"""
    return PostgresTargetWriter()


async def load_configs(
    session: AsyncSession, etl_table_pid: int | None
) -> list[EtlTableConfig]:
    """載入表設定;排程指定單表(etl_table_pid 非 NULL)時只取該表。"""
    configs = await load_table_configs(session)
    if etl_table_pid is None:
        return configs
    return [c for c in configs if c.etl_table_pid == etl_table_pid]


async def _mark_failed_if_dangling(
    store: RunStateTracker, configs: Sequence[EtlTableConfig], exc: Exception
) -> None:
    """run 已建立但未收尾 → 補標 failed(不可留 running 殭屍狀態)。"""
    if store.created_run_pid is None or store.run_finished:
        return
    try:
        await store.finish_run(
            store.created_run_pid,
            status="failed",
            total_tables=len(configs),
            success_tables=0,
            failed_tables=0,
            error_message=mask_secrets(str(exc)),
        )
    except Exception:
        # 補標 failed 本身失敗只記 log,原始例外仍向外拋
        logger.exception("run 補標 failed 失敗:run_pid=%s", store.created_run_pid)


@broker.task(task_name="run_etl")
async def run_etl(
    trigger_type: str = "manual",
    schedule_pid: int | None = None,
    etl_table_pid: int | None = None,
) -> dict[str, object]:
    """執行一輪 ETL:建 run 紀錄 → 逐表管線;引擎外例外把 run 補標 failed 後再拋。"""
    async with AsyncSessionLocal() as session:
        store = RunStateTracker(make_store(session))
        configs = await load_configs(session, etl_table_pid)
        try:
            result = await run_etl_pipeline(
                configs,
                reader=make_reader(),
                writer=make_writer(),
                store=store,
                trigger_type=trigger_type,
                schedule_pid=schedule_pid,
            )
        except Exception as exc:
            logger.exception(
                "ETL run 執行失敗(引擎外例外):trigger_type=%s schedule_pid=%s",
                trigger_type,
                schedule_pid,
            )
            # 先清掉 session 內可能殘留的失敗交易,補標 failed 才能落 DB
            await session.rollback()
            await _mark_failed_if_dangling(store, configs, exc)
            raise
        return asdict(result)
