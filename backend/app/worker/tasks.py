"""worker task:`mirror_sync` — 排程 / 手動觸發的自動鏡像同步執行入口。

worker 啟動指令(供 task-012 容器 command 使用):

    uv run taskiq worker app.worker.tasks:broker

流程:建立 `etl_runs` 紀錄(store.create_run)→ 逐表鏡像同步 →
任何引擎外例外都把 run 補標 failed + log 錯誤明細,不留 running 殭屍狀態。
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis as cache
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.core.logging import setup_logging
from app.etl.engine import (
    DbRunStore,
    EtlTableConfig,
    RunStore,
    mask_secrets,
)
from app.etl.mirror import MirrorEngine, TableStat, stat_changed
from app.models.rds_table_meta import Dataset, RdsTableMeta
from app.repositories.rds_table_meta_repo import RdsTableMetaRepository
from app.utils.datetime import db_now, now_tw
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

    async def create_run(
        self, *, trigger_type: str, schedule_pid: int | None, total_tables: int
    ) -> int:
        run_pid = await self._inner.create_run(
            trigger_type=trigger_type, schedule_pid=schedule_pid, total_tables=total_tables
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


# ── task-004:自動鏡像同步(mirror_sync)───────────────────────────────────
# 重用既有 run store(DbRunStore / RunStateTracker)與逐表 log 慣例;鏡像引擎為 task-003。


def make_mirror() -> MirrorEngine:
    """建立自動鏡像引擎(來源 / 目標 RDS lazy 連線);測試可 monkeypatch 注入 fake。"""
    return MirrorEngine()


def _mirror_config(schema: str, table: str) -> EtlTableConfig:
    """為 run store 逐表 log 組最小 config:鏡像保留 schema.table 識別,無 mapping。"""
    return EtlTableConfig(
        etl_table_pid=None,
        source_schema=schema,
        source_table=table,
        target_schema=schema,
        target_table=table,
        is_enabled=True,
    )


def _sync_elapsed_ms(started: datetime) -> int:
    return max(int((now_tw() - started).total_seconds() * 1000), 0)


async def _resolve_sync_targets(
    mirror: MirrorEngine,
    schema: str | None,
    table: str | None,
    tables: list[str] | None = None,
) -> list[tuple[str, str]]:
    """篩選(schema+tables)→ 該清單;單表(schema+table)→ 該表;全量(皆空)→ 全來源表。"""
    if tables is not None:
        if schema is None:
            raise ValueError("tables 指定時 schema 必填")
        return [(schema, t) for t in tables]
    if schema is not None and table is not None:
        return [(schema, table)]
    if schema is None and table is None:
        return await mirror.list_source_tables()
    raise ValueError("schema 與 table 須同時提供或同時省略")


async def _mark_meta_synced(
    session: AsyncSession,
    repo: RdsTableMetaRepository,
    schema: str,
    table: str,
    written: int,
) -> None:
    """更新該來源表快照的同步 / 轉換時間與 row_count(同步狀態顯示於原始資料管理頁 → source)。

    row_count 取自 mirror 實寫筆數(免 COUNT(*));repo 無 row_count-only 方法且禁改 repo,
    故就地更新該欄(範圍對齊 mark_synced 的未刪除條件)。
    """
    await repo.mark_synced(Dataset.SOURCE, schema, table, actor_uid=SYSTEM_ACTOR_UID)
    await repo.mark_transformed(Dataset.SOURCE, schema, table, actor_uid=SYSTEM_ACTOR_UID)
    await session.execute(
        update(RdsTableMeta)
        .where(
            RdsTableMeta.dataset == Dataset.SOURCE,
            RdsTableMeta.schema_name == schema,
            RdsTableMeta.table_name == table,
            RdsTableMeta.is_deleted.is_(False),
        )
        .values(row_count=written, updated_by=SYSTEM_ACTOR_UID, updated_at=db_now())
    )
    await session.flush()


@broker.task(task_name="mirror_sync")
async def mirror_sync(
    schema: str | None = None,
    table: str | None = None,
    tables: list[str] | None = None,
    incremental: bool = False,
    trigger_type: str = "manual",
    schedule_pid: int | None = None,
) -> dict[str, object]:
    """執行一輪自動鏡像同步:建 run → 逐表鏡像(來源 → hub,套字典 COMMENT)→ 更新快照 → 收尾 run。

    - 篩選:schema + tables 清單;單表:schema + table 皆給;全量:皆空(worker 端 DS 優先)。
    - incremental=True(增量同步):先讀來源計數器 signature 與基準,未變動表跳過(skip log,
      不重灌、last_synced_at 不更新)。排除語意改由排程啟停決定(停用排程 → 不在
      scheduler 派工的 tables 內),此處不再讀取逐表排除旗標。
    - incremental=False(人工全量同步):忽略偵測,整批覆蓋指定 / 全部表(對齊既有語意);
      但仍更新 signature 基準,供後續增量比對(人工全量為保底重灌路徑)。
    - 單表失敗不中斷整輪:錯誤明細(含 stack trace,機密遮罩)寫入該表 log,續跑下一表;
      任一表失敗 → run 總狀態 failed(對齊既有 run 收尾慣例)。
    - 同步後失效 datasets:source:* 快取(對齊 snapshot_service 失效用法)。
    """
    async with AsyncSessionLocal() as session:
        store = RunStateTracker(make_store(session))
        mirror = make_mirror()
        repo = RdsTableMetaRepository(session)
        configs: list[EtlTableConfig] = []
        try:
            targets = await _resolve_sync_targets(mirror, schema, table, tables)
            configs = [_mirror_config(s, t) for s, t in targets]
            # 一次取來源全表累計計數器(零掃表);增量模式再讀 signature 基準
            stats = await mirror.fetch_source_stats()
            baselines: dict[tuple[str, str], tuple[int, int, int] | None] = {}
            if incremental:
                baselines = await repo.read_stat_baselines(Dataset.SOURCE)
            run_pid = await store.create_run(
                trigger_type=trigger_type,
                schedule_pid=schedule_pid,
                total_tables=len(configs),
            )
            skipped = 0

            # 增量 skip 表不進併發池:序列判斷未變動表 → skip log,其餘進 to_sync 併發同步。
            # (skip log 寫自有 DB,亦須序列;此處在主協程序列處理,天然安全)
            to_sync: list[EtlTableConfig] = []
            for config in configs:
                key = (config.source_schema, config.source_table)
                # 增量:未變動表跳過(不重灌、last_synced_at 不更新);
                # current 為 None(來源無計數)保守視為變動,避免漏灌
                if incremental:
                    current = stats.get(key)
                    baseline_tuple = baselines.get(key)
                    baseline = (
                        None if baseline_tuple is None else TableStat(*baseline_tuple)
                    )
                    current_stat = current or TableStat(0, 0, 0)
                    changed = current is None or stat_changed(current_stat, baseline)
                    if not changed:
                        await store.add_skipped_log(run_pid=run_pid, config=config)
                        skipped += 1
                        continue
                to_sync.append(config)

            # 表級併發:僅 mirror.mirror_table(s, t)(讀寫 RDS,各 call 自連線池取連線)併發;
            # 所有自有 DB 寫入(start/finish_table_log、_mark_meta_synced、update_stat_signature)
            # 共用同一 AsyncSession → 以單一 db_lock 序列化,禁跨協程同時使用 session。
            # 前提:字典 COMMENT 讀自來源 DB,不依賴目標 DS 表先落地 → 表間無順序硬依賴,可併發。
            # SYNC_CONCURRENCY=1 時 semaphore 逐一放行 → 行為(含 log 順序)等同現行序列版。
            concurrency = max(get_settings().SYNC_CONCURRENCY, 1)
            sem = asyncio.Semaphore(concurrency)
            db_lock = asyncio.Lock()

            async def _sync_one(config: EtlTableConfig) -> bool:
                """同步單表:回傳 True(成功)/ False(失敗);計數由回傳值收斂,禁 race。"""
                s, t = config.source_schema, config.source_table
                # 來源 pg_stat 無此表計數 → 保守以 (0,0,0) 為 signature 基準值
                current_stat = stats.get((s, t)) or TableStat(0, 0, 0)
                async with sem:
                    started = now_tw()
                    async with db_lock:
                        log_pid = await store.start_table_log(
                            run_pid=run_pid, config=config
                        )
                    try:
                        written = await mirror.mirror_table(s, t)
                    except Exception as exc:
                        logger.exception("同步單表失敗:%s.%s", s, t)
                        async with db_lock:
                            await store.finish_table_log(
                                log_pid,
                                status="failed",
                                row_count=None,
                                duration_ms=_sync_elapsed_ms(started),
                                error_message=mask_secrets(str(exc)),
                                error_stack=mask_secrets(traceback.format_exc()),
                            )
                        return False
                    async with db_lock:
                        await _mark_meta_synced(session, repo, s, t, written)
                        # 覆蓋成功 → 更新 signature 基準(全量模式亦更新,建立/刷新基準)
                        await repo.update_stat_signature(
                            Dataset.SOURCE,
                            s,
                            t,
                            n_tup_ins=current_stat.n_tup_ins,
                            n_tup_upd=current_stat.n_tup_upd,
                            n_tup_del=current_stat.n_tup_del,
                            actor_uid=SYSTEM_ACTOR_UID,
                        )
                        await store.finish_table_log(
                            log_pid,
                            status="success",
                            row_count=written,
                            duration_ms=_sync_elapsed_ms(started),
                            error_message=None,
                            error_stack=None,
                        )
                    logger.info("同步單表完成:%s.%s(%d 筆)", s, t, written)
                    return True

            # 單表失敗不中斷整輪:_sync_one 內部吞例外並回傳 False,gather 全數跑完
            results = await asyncio.gather(*(_sync_one(cfg) for cfg in to_sync))
            success = sum(1 for ok in results if ok)
            failed = len(results) - success
            status = "failed" if failed else "success"
            await store.finish_run(
                run_pid,
                status=status,
                total_tables=len(configs),
                success_tables=success,
                failed_tables=failed,
                error_message=f"{failed} 表失敗" if failed else None,
            )
            # 同步改動 source 快照的同步時間 / row_count → 失效原始資料管理清單快取
            await cache.delete_pattern(cache.cache_key("datasets", Dataset.SOURCE.value, "*"))
            return {
                "run_pid": run_pid,
                "status": status,
                "total_tables": len(configs),
                "success_tables": success,
                "failed_tables": failed,
                "skipped_tables": skipped,
            }
        except Exception as exc:
            logger.exception("同步執行失敗(引擎外例外):schema=%s table=%s", schema, table)
            await session.rollback()
            await _mark_failed_if_dangling(store, configs, exc)
            raise
        finally:
            await mirror.dispose()
