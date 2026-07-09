---
id: task-001
title: 同輪表級平行同步(worker 併發 + SYNC_CONCURRENCY env)
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/worker/tasks.py
  - backend/app/core/config.py
  - backend/tests/test_mirror_sync_parallel.py
  - docker-compose.yml
  - docker-compose-staging.yml
  - docker-compose-production.yml
  - .env.example
  - .env.staging.example
  - .env.production.example
estimated_hours: 4
model: opus
effort: high
---

## 目標

`mirror_sync` 內逐表 for 迴圈改為固定並行度的 asyncio 併發(預設 2,env `SYNC_CONCURRENCY` 可調),多表輪次 wall-clock 顯著下降;既有語意(單表失敗不中斷、逐表 log、run 收尾統計、增量 skip)完全不變。

## 實作要點

1. `core/config.py` Settings 加 `SYNC_CONCURRENCY: int = 2`(僅 worker 讀;沿用既有 env 化註解風格)。
2. `worker/tasks.py` `mirror_sync`:
   - 逐表迴圈改 `asyncio.Semaphore(settings.SYNC_CONCURRENCY)` + `asyncio.gather`(per-table coroutine)。
   - **併發僅及 `mirror.mirror_table(s, t)`(讀寫 RDS,各 call 自連線池取連線,天然安全)**;所有自有 DB 寫入(store.start/finish_table_log、`_mark_meta_synced`、`update_stat_signature`、skip log)共用同一 `AsyncSession` → 以單一 `asyncio.Lock` 序列化,**禁**跨協程同時使用 session。
   - 增量 skip 判斷與計數(success/failed/skipped)彙總邏輯不變;計數器更新亦在 lock 內(或以回傳值收斂後統加,擇一,禁 race)。
   - `SYNC_CONCURRENCY=1` 時行為(含 log 順序語意)等同現行序列版。
   - DS 排序保留(list 順序即派發順序);字典 COMMENT 讀自來源 DB,不依賴目標 DS 表先落地,故併發無順序硬依賴 — 在程式註解記明此前提。
3. 三個 compose 的 **worker 服務** environment 加 `SYNC_CONCURRENCY: ${SYNC_CONCURRENCY:-2}`(本地 docker-compose.yml 用 `- KEY=VAL` 風格對齊現有);三個 `.env*.example` 登記(附「調高→來源 RDS 讀壓上升,異常設回 1」說明)。
4. **禁**動 `mirror.py` / `engine.py`(002 會動 engine.py,互鎖);**禁**動既有測試檔,新測試寫 `tests/test_mirror_sync_parallel.py`(fake mirror 記錄併發峰值/完成表集合,不連真 RDS,風格對齊 `test_mirror_sync_tables_v131.py`)。

## Acceptance

- [x] `uv run pytest tests/test_mirror_sync_parallel.py` 全綠(4 passed),涵蓋:併發度>1 時全部表各恰好一筆 log 且 run 統計正確;任一表失敗整輪 failed 且其餘表照跑;`SYNC_CONCURRENCY=1` 行為同現行;增量 skip 表不進併發池。
- [x] `uv run pytest`(既有測試不壞)— 於 HEAD 建乾淨 worktree 僅套本 task 3 檔驗證;mirror 相關測試(incremental/tables_v131/mirror)全綠。完整套件的間歇失敗經定位為多 worker 共用測試 DB(localhost:5435)之併發爭用(FK/unique 違反、密碼認證等,每次失敗集合不同),非本 task 迴歸。
- [x] `uv run ruff check .` 通過;`uv run mypy .` 無新增錯誤(基線 39 → 改後 39,本 task 3 檔 0 錯)
- [x] `docker compose config`、`docker compose -f docker-compose-staging.yml config`、`docker compose -f docker-compose-production.yml config` 皆解析成功且 worker 服務含 `SYNC_CONCURRENCY`(=2)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/08-performance.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/00-overview/02-secrets.md`
- `docs/Design-Base/00-overview/03-env-layers.md`
- `docs/Design-Base/06-Coolify-CD/01-compose.md`
- `docs/Design-Base/04-databases/07-connection.md`
