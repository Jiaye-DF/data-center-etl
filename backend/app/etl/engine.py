"""ETL 執行核心的共用原語(v1.3.1):run store / 表設定 dataclass / reader-writer Protocol。

v1.3.1 起排程單一化為自動鏡像同步(`app.etl.mirror` + `worker.mirror_sync`),
v1.1 config-ETL 逐表管線(舊 ETL task 與表設定載入器)已下線移除;
本模組保留 mirror_sync 仍共用的原語:

- `etl_runs` / `etl_run_logs` 寫入介面 `RunStore` 與其 SQLAlchemy 實作 `DbRunStore`。
- 單表設定快照 `EtlTableConfig`、一輪彙總結果 `EtlRunResult`。
- 來源 / 目標串流 Protocol `SourceReader` / `TargetWriter`(production 用 Postgres 實作)。
- 錯誤明細機密遮罩 `mask_secrets`(禁密碼隨錯誤落 DB / log)。
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterable, AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.reader import DEFAULT_BATCH_SIZE
from app.etl.transforms import ColumnMapping
from app.models import EtlRun, EtlRunLog

# 時間工具統一自 app/utils/datetime.py import(05-timezone.md;fixed.md §5 收口搬移)
from app.utils.datetime import db_now as _db_now

logger = logging.getLogger(__name__)

# 錯誤訊息 / stack trace 落 DB 前須遮罩的機密 env(02-secrets.md § Log / error 過濾)
_SECRET_ENV_KEYS = ("AWS_RDS_PASSWORD",)


def mask_secrets(message: str) -> str:
    """把 env 中的 DB 密碼值自訊息中遮罩,禁密碼隨錯誤明細落 DB / log。"""
    masked = message
    for key in _SECRET_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            masked = masked.replace(value, "****")
    return masked


@dataclass(frozen=True)
class EtlTableConfig:
    """單表 ETL 設定快照(etl_tables 一列 + 其啟用中 mappings)。"""

    etl_table_pid: int | None
    source_schema: str
    source_table: str
    target_schema: str
    target_table: str
    is_enabled: bool
    mappings: tuple[ColumnMapping, ...] = ()


@dataclass(frozen=True)
class EtlRunResult:
    """一輪 ETL 的彙總結果。"""

    run_pid: int
    status: str
    total_tables: int
    success_tables: int
    failed_tables: int
    skipped_tables: int


class SourceReader(Protocol):
    """來源讀取介面(production:reader.PostgresSourceReader);分批串流,禁整表物化。"""

    def stream_rows(
        self,
        schema: str,
        table: str,
        columns: Sequence[str],
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> AsyncIterator[list[dict[str, object]]]: ...


class TargetWriter(Protocol):
    """目標寫入介面(production:writer.PostgresTargetWriter);收分批迭代器逐批寫入。"""

    async def write_table(
        self,
        *,
        schema: str,
        table: str,
        columns: Sequence[str],
        column_types: Mapping[str, str | None],
        row_batches: AsyncIterable[Sequence[Mapping[str, object]]],
        comment_statements: Sequence[str],
    ) -> int: ...


class RunStore(Protocol):
    """etl_runs / etl_run_logs 寫入介面(production:DbRunStore;測試可用 in-memory fake)。"""

    async def create_run(
        self, *, trigger_type: str, schedule_pid: int | None, total_tables: int
    ) -> int: ...

    async def start_table_log(self, *, run_pid: int, config: EtlTableConfig) -> int: ...

    async def finish_table_log(
        self,
        log_pid: int,
        *,
        status: str,
        row_count: int | None,
        duration_ms: int | None,
        error_message: str | None,
        error_stack: str | None,
    ) -> None: ...

    async def add_skipped_log(self, *, run_pid: int, config: EtlTableConfig) -> None: ...

    async def finish_run(
        self,
        run_pid: int,
        *,
        status: str,
        total_tables: int,
        success_tables: int,
        failed_tables: int,
        error_message: str | None,
    ) -> None: ...


class DbRunStore:
    """RunStore 的 SQLAlchemy 實作:逐表即時 commit,單表失敗也保留已寫入的 log。"""

    def __init__(self, session: AsyncSession, *, actor_uid: UUID) -> None:
        self._session = session
        self._actor_uid = actor_uid

    async def create_run(
        self, *, trigger_type: str, schedule_pid: int | None, total_tables: int
    ) -> int:
        run = EtlRun(
            trigger_type=trigger_type,
            schedule_pid=schedule_pid,
            status="running",
            started_at=_db_now(),
            total_tables=total_tables,
            created_by=self._actor_uid,
            updated_by=self._actor_uid,
        )
        self._session.add(run)
        await self._session.flush()
        run_pid = run.pid
        await self._session.commit()
        return run_pid

    async def start_table_log(self, *, run_pid: int, config: EtlTableConfig) -> int:
        log = EtlRunLog(
            etl_run_pid=run_pid,
            etl_table_pid=config.etl_table_pid,
            source_schema=config.source_schema,
            source_table=config.source_table,
            status="running",
            started_at=_db_now(),
            created_by=self._actor_uid,
            updated_by=self._actor_uid,
        )
        self._session.add(log)
        await self._session.flush()
        log_pid = log.pid
        await self._session.commit()
        return log_pid

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
        log = await self._session.get(EtlRunLog, log_pid)
        if log is None:
            raise RuntimeError(f"etl_run_logs 不存在:pid={log_pid}")
        log.status = status
        log.row_count = row_count
        log.duration_ms = duration_ms
        log.finished_at = _db_now()
        log.error_message = error_message
        log.error_stack = error_stack
        log.updated_at = _db_now()
        log.updated_by = self._actor_uid
        await self._session.commit()

    async def add_skipped_log(self, *, run_pid: int, config: EtlTableConfig) -> None:
        now = _db_now()
        log = EtlRunLog(
            etl_run_pid=run_pid,
            etl_table_pid=config.etl_table_pid,
            source_schema=config.source_schema,
            source_table=config.source_table,
            status="skipped",
            started_at=now,
            finished_at=now,
            created_by=self._actor_uid,
            updated_by=self._actor_uid,
        )
        self._session.add(log)
        await self._session.commit()

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
        run = await self._session.get(EtlRun, run_pid)
        if run is None:
            raise RuntimeError(f"etl_runs 不存在:pid={run_pid}")
        run.status = status
        run.finished_at = _db_now()
        run.total_tables = total_tables
        run.success_tables = success_tables
        run.failed_tables = failed_tables
        run.error_message = error_message
        run.updated_at = _db_now()
        run.updated_by = self._actor_uid
        await self._session.commit()
