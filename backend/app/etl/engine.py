"""ETL 執行核心:DB 設定驅動(etl_tables / etl_mappings)的逐表 讀 → 轉換 → 寫 管線。

- 只處理啟用表;停用表記 skipped log 後跳過。
- 逐表寫 `etl_runs` / `etl_run_logs`:起訖時間、筆數、耗時、狀態;
  單表失敗捕捉例外寫入錯誤明細(含 stack trace,機密遮罩後)再續跑下一表,
  run 總狀態標 failed。
- reader / writer / store 以 Protocol 注入:production 用 Postgres 實作與 DbRunStore,
  單元測試可用 in-memory fake(不需連真 RDS)。
"""

from __future__ import annotations

import logging
import os
import traceback
from collections.abc import AsyncIterable, AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.comments import build_column_comments
from app.etl.reader import DEFAULT_BATCH_SIZE
from app.etl.transforms import ColumnMapping, map_row
from app.models import EtlMapping, EtlRun, EtlRunLog, EtlTable

# 時間工具統一自 app/utils/datetime.py import(05-timezone.md;fixed.md §5 收口搬移)
from app.utils.datetime import db_now as _db_now
from app.utils.datetime import now_tw

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

    async def create_run(self, *, trigger_type: str, schedule_pid: int | None) -> int: ...

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

    async def create_run(self, *, trigger_type: str, schedule_pid: int | None) -> int:
        run = EtlRun(
            trigger_type=trigger_type,
            schedule_pid=schedule_pid,
            status="running",
            started_at=_db_now(),
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


async def load_table_configs(session: AsyncSession) -> list[EtlTableConfig]:
    """自自有 DB 載入全部未刪除表設定(含停用表;停用由 run_etl 記 skipped)。"""
    tables = (
        (
            await session.execute(
                select(EtlTable).where(EtlTable.is_deleted.is_(False)).order_by(EtlTable.pid)
            )
        )
        .scalars()
        .all()
    )
    configs: list[EtlTableConfig] = []
    for tbl in tables:
        mappings = (
            (
                await session.execute(
                    select(EtlMapping)
                    .where(
                        EtlMapping.etl_table_pid == tbl.pid,
                        EtlMapping.is_deleted.is_(False),
                    )
                    .order_by(EtlMapping.sort_order, EtlMapping.pid)
                )
            )
            .scalars()
            .all()
        )
        configs.append(
            EtlTableConfig(
                etl_table_pid=tbl.pid,
                source_schema=tbl.source_schema,
                source_table=tbl.source_table,
                target_schema=tbl.target_schema,
                target_table=tbl.target_table,
                is_enabled=tbl.is_enabled,
                mappings=tuple(
                    ColumnMapping(
                        source_column=m.source_column,
                        target_column=m.target_column,
                        transform_type=m.transform_type,
                        comment=m.comment,
                    )
                    for m in mappings
                ),
            )
        )
    return configs


def _elapsed_ms(started: datetime) -> int:
    return max(int((now_tw() - started).total_seconds() * 1000), 0)


def _split_source_tables(source_table: str) -> list[str]:
    """解析 etl_tables.source_table:多來源以逗號合併(fixed.md §2 約定)。"""
    return [t.strip() for t in source_table.split(",") if t.strip()]


async def _iter_rows(
    reader: SourceReader, schema: str, table: str, columns: Sequence[str]
) -> AsyncIterator[dict[str, object]]:
    """把分批串流攤平成逐列迭代(多來源 zip 用)。"""
    async for batch in reader.stream_rows(schema, table, columns):
        for row in batch:
            yield row


async def _stream_source_rows(
    config: EtlTableConfig, reader: SourceReader
) -> AsyncIterator[list[dict[str, object]]]:
    """分批串流來源列;多來源表以列位置並排合併(zip,缺列補 None)。

    - 單來源:source_column 為裸欄名,分批原樣往下傳。
    - 多來源(source_table 逗號合併,fixed.md §2 約定):source_column 須為
      `<來源表>.<欄名>` 限定名;各來源逐列 zip 合併後重新分批,合併列以限定名為鍵,
      map_row 直接以 mapping 的 source_column 取值。並排合併對齊 v1.0.0
      m2201_job 佔位語意(無真實 join key)。
    - 全程僅保留單批在記憶體(scan AD-006)。
    """
    tables = _split_source_tables(config.source_table)
    if not tables:
        raise ValueError(f"表設定 source_table 為空:{config.source_table!r}")
    if len(tables) == 1:
        columns = list(dict.fromkeys(m.source_column for m in config.mappings))
        async for batch in reader.stream_rows(config.source_schema, tables[0], columns):
            yield batch
        return

    columns_by_table: dict[str, list[str]] = {t: [] for t in tables}
    for m in config.mappings:
        table, sep, column = m.source_column.partition(".")
        if not sep or not column or table not in columns_by_table:
            raise ValueError(
                f"多來源表 {config.source_table} 的 mapping 來源欄須為 <來源表>.<欄名>:"
                f"{m.source_column!r}"
            )
        if column not in columns_by_table[table]:
            columns_by_table[table].append(column)

    # 被 mapping 引用的來源表才讀;各表逐列並排 zip,短表以 None 補齊
    active = {t: cols for t, cols in columns_by_table.items() if cols}
    iters: dict[str, AsyncIterator[dict[str, object]]] = {
        t: _iter_rows(reader, config.source_schema, t, cols) for t, cols in active.items()
    }
    exhausted: set[str] = set()
    merged: list[dict[str, object]] = []
    while True:
        row: dict[str, object] = {}
        got_any = False
        for table, columns in active.items():
            source_row: dict[str, object] | None = None
            if table not in exhausted:
                source_row = await anext(iters[table], None)
                if source_row is None:
                    exhausted.add(table)
                else:
                    got_any = True
            for column in columns:
                row[f"{table}.{column}"] = None if source_row is None else source_row.get(column)
        if not got_any:
            break
        merged.append(row)
        if len(merged) >= DEFAULT_BATCH_SIZE:
            yield merged
            merged = []
    if merged:
        yield merged


async def _transform_batches(
    config: EtlTableConfig, reader: SourceReader
) -> AsyncIterator[list[dict[str, object]]]:
    """逐批轉換:來源批 → map_row 目標批(記憶體僅保留單批)。"""
    async for batch in _stream_source_rows(config, reader):
        yield [map_row(row, config.mappings) for row in batch]


async def _process_table(
    config: EtlTableConfig, *, reader: SourceReader, writer: TargetWriter
) -> int:
    """單表管線:驗 mapping / comment 完整性 → 分批 讀 → 轉換 → 寫;回傳寫入筆數。

    讀寫全程串流分批(scan AD-006);writer 端單交易,任一批失敗整表 rollback。
    """
    if not config.mappings:
        raise ValueError(f"表 {config.source_schema}.{config.source_table} 無欄位 mapping 設定")
    target_columns = [m.target_column for m in config.mappings]
    comments = {m.target_column: m.comment for m in config.mappings}
    # 先驗 comment 完整性(缺 / 空即 raise,不靜默),再進讀寫
    comment_statements = build_column_comments(
        config.target_table, target_columns, comments, schema=config.target_schema
    )
    column_types: dict[str, str | None] = {
        m.target_column: m.transform_type for m in config.mappings
    }
    return await writer.write_table(
        schema=config.target_schema,
        table=config.target_table,
        columns=target_columns,
        column_types=column_types,
        row_batches=_transform_batches(config, reader),
        comment_statements=comment_statements,
    )


async def run_etl(
    configs: Sequence[EtlTableConfig],
    *,
    reader: SourceReader,
    writer: TargetWriter,
    store: RunStore,
    trigger_type: str = "manual",
    schedule_pid: int | None = None,
) -> EtlRunResult:
    """執行一輪 ETL:逐表 讀 → 轉換 → 寫 + 詳細 log。

    - 停用表記 skipped 後跳過。
    - 單表失敗不中斷整個 run:錯誤明細(含 stack trace,機密遮罩後)寫入該表 log,
      續跑下一表;任一表失敗 → run 總狀態 failed。
    """
    run_pid = await store.create_run(trigger_type=trigger_type, schedule_pid=schedule_pid)
    success = failed = skipped = 0
    for config in configs:
        if not config.is_enabled:
            await store.add_skipped_log(run_pid=run_pid, config=config)
            skipped += 1
            logger.info("停用表跳過:%s.%s", config.source_schema, config.source_table)
            continue
        started = now_tw()
        log_pid = await store.start_table_log(run_pid=run_pid, config=config)
        try:
            row_count = await _process_table(config, reader=reader, writer=writer)
        except Exception as exc:
            failed += 1
            # 逐表例外:寫入錯誤明細(含 stack trace)後續跑下一表
            logger.exception(
                "ETL 單表失敗:%s.%s", config.source_schema, config.source_table
            )
            await store.finish_table_log(
                log_pid,
                status="failed",
                row_count=None,
                duration_ms=_elapsed_ms(started),
                error_message=mask_secrets(str(exc)),
                error_stack=mask_secrets(traceback.format_exc()),
            )
            continue
        success += 1
        await store.finish_table_log(
            log_pid,
            status="success",
            row_count=row_count,
            duration_ms=_elapsed_ms(started),
            error_message=None,
            error_stack=None,
        )
        logger.info(
            "ETL 單表完成:%s.%s → %s.%s(%d 筆)",
            config.source_schema,
            config.source_table,
            config.target_schema,
            config.target_table,
            row_count,
        )
    status = "failed" if failed else "success"
    await store.finish_run(
        run_pid,
        status=status,
        total_tables=len(configs),
        success_tables=success,
        failed_tables=failed,
        error_message=f"{failed} 表失敗" if failed else None,
    )
    return EtlRunResult(
        run_pid=run_pid,
        status=status,
        total_tables=len(configs),
        success_tables=success,
        failed_tables=failed,
        skipped_tables=skipped,
    )
