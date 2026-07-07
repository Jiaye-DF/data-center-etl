---
id: task-004
title: 增量同步整合(mirror_sync 加偵測→只灌變動表→skip log→更新基準)
status: done
parallel: true
depends_on: [task-002, task-003]
affected_files:
  - backend/app/worker/tasks.py
  - backend/tests/test_mirror_sync_incremental.py
estimated_hours: 4
---

## 目標

`mirror_sync` worker task 加**增量模式**:讀來源計數器(task-002)與自有 DB 基準(task-003)比對,**只對變動表**走既有整批覆蓋,未變動表寫 **skipped** log 且**不更新** `last_synced_at`;同步成功後更新該表計數器基準。人工「全量同步」(`incremental=False`,現行語意)強制覆蓋全部表、忽略偵測。

> 同一個 `mirror_sync` 支援兩種觸發:taskiq 自動(task-005 帶 `trigger_type="schedule"`)與人工手動(預設 `"manual"`);差別只在 `trigger_type` 標記,操作本身相同。

## 設計要點

- `mirror_sync(schema=None, table=None, tables=None, incremental: bool = False, trigger_type: str = "manual")`:
  - `trigger_type` 透傳 `store.create_run(trigger_type=trigger_type, ...)`,使 run 正確標記「排程 / 手動」(既有 `etl_runs.trigger_type`,check 約束 `schedule`/`manual`)。既有手動呼叫端(`SyncService`)不帶此參數 → 預設 `"manual"`,無需改動 `sync_service.py`。
  - **`incremental=False`(預設,人工全量 / `sync_all` / 單表 / 篩選,語意不變)**:沿用現行流程,對 `_resolve_sync_targets` 得到的每張表都 `mirror.mirror_table`。**額外**:成功後除既有 `_mark_meta_synced` 外,一併 `repo.update_signature`(以「同步當下」該表 signature)寫基準——使全量同步後建立/刷新基準(對齊 propose「首次/新表基準建立」)。
  - **`incremental=True`(排程派工,task-005 帶入)**:
    1. `sigs_current = await mirror.fetch_source_signatures()`;`sigs_prev = await repo.get_signatures(Dataset.SOURCE)`;`excluded = await repo.get_excluded_tables(Dataset.SOURCE)`。
    1a. **先剔除被排除的表**:`targets = [(s, t) for (s, t) in targets if (s, t) not in excluded]`(被排除表不納入夜間增量,對齊 propose ⑦「可逐表排除」;不建 log、不計入 run 統計)。**僅增量路徑套排除**;`incremental=False`(人工全量)忽略排除、強制覆蓋全部。
    2. 對每個(未被排除的)target 表:`prev = sigs_prev.get((schema, table))`(轉 `StatSignature | None`),`current = sigs_current.get((schema, table))`。
       - `current is None`(來源已不在 pg_stat / track_counts 未開)→ 保守視為變動(仍嘗試整灌)或依既有錯誤處理;記 log。
       - `is_table_changed(prev, current)` 為 `False` → `store.add_skipped_log(run_pid, config)`(既有方法,狀態 `skipped`),**不** `mirror_table`、**不** `mark_synced`(hub `last_synced_at` 不更新)。
       - `True` → `mirror.mirror_table` → `_mark_meta_synced` → `repo.update_signature(current)` → success log。
    3. run 收尾:`total_tables` / `success_tables` / `failed_tables` 沿用;skipped 由 run_logs 呈現(可另回傳 `skipped_tables` 統計)。
  - 單表失敗不中斷整輪(沿用既有 try/except + 機密遮罩 stack);任一失敗 → run failed。
  - 同步後失效 `datasets:source:*` cache(沿用既有 `cache.delete_pattern`)。
  - **禁**改 config-driven `run_etl` 邏輯;`mirror.mirror_table`(TRUNCATE + 重灌,禁 DROP)不改。
- 回傳 dict 加 `incremental`(bool)與 `skipped_tables`(int),供上層 / 測試斷言。

## Acceptance

- [x] `cd backend && uv run pytest tests/test_mirror_sync_incremental.py -q` 全綠(fake MirrorEngine + monkeypatch repo,免連 RDS),涵蓋:
  - 某表基準與當前 signature 相同 → 該表產生 `skipped` log、**未**呼叫 `mirror_table`、`last_synced_at` 未更新
  - 某表計數器增加 → 判定變動、呼叫 `mirror_table`、`update_signature` 被以當前 signature 呼叫
  - 某表無基準(prev=None)→ 判定變動並整灌(首次基準建立)
  - 計數器倒退 → 判定變動並整灌
  - `incremental=True` 且某表 `sync_excluded` → 該表**完全不處理**(無 mirror_table、無 log、不計入 total)
  - `incremental=False` → 全部 target 表都整灌(**忽略偵測與排除**),且成功表都寫基準
- [x] `uv run python -c "import inspect; from app.worker.tasks import mirror_sync; p=inspect.signature(mirror_sync).parameters; print('incremental' in p, 'trigger_type' in p)"` 印出 `True True`
- [x] 測試斷言 `trigger_type` 透傳:以 `trigger_type='schedule'` 呼叫 → 建立的 run `trigger_type=='schedule'`;預設呼叫 → `'manual'`
- [x] `git diff backend/app/worker/tasks.py` 未改動 `run_etl` task 內文(僅動 `mirror_sync` 相關)
- [x] `uv run ruff check . && uv run mypy app` green

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/08-performance.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/00-overview/05-timezone.md`
