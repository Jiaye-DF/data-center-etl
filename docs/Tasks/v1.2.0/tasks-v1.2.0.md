# Tasks v1.2.0

> 狀態:全部完成(已完成 6/6)
> 變更:2026-07-06 propose 加「業務資料名稱(GAT JOIN 快照落地)」→ 影響 task-001(model 加 `business_name`)/ task-002(refresh 做 GAT JOIN 寫入 + list 回傳)/ task-005(前端加業務資料名稱欄);無新增檔案、依賴鏈不變。
> 來源:`propose-v1.2.0.md`(scope 地板,禁動)
> 範圍:自動偵測同步平台 —— DB metadata 快照(+Redis)、自動鏡像 + DS 字典中文 COMMENT 引擎、雙瀏覽頁補強、排程友善 UI。既有 `app/etl/{engine,reader,writer,comments}.py`(config-driven 路徑)**保留不動**,自動鏡像為新路徑。
> 起點:dev-v1.2/auto-sync(雙瀏覽頁 + 內省 API 已於 cf9d324 / 1918932 落地);本版於其上補強改讀快照。
> 執行環境註記:各 task Acceptance 指令為 bash 語法;本機為 Windows,worker 一律以 **Git Bash** 或 PowerShell 對應執行。RDS 連線走 `.env` `AWS_RDS_*`(未進 git)。

## 清單

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | metadata 快照資料模型 + migration + 依賴鎖版(redis) | done | ✓ | — | `backend/app/models/rds_table_meta.py` / `models/__init__.py` / `alembic/versions/v2_add_rds_table_meta.py` / `pyproject.toml` / `uv.lock` / `tests/test_models_v120.py` |
| 002 | 快照服務 + Redis cache + datasets API 改讀快照(過濾/時間欄/重整) | done | ✓ | 001 | `backend/app/services/snapshot_service.py` / `repositories/rds_table_meta_repo.py` / `core/redis.py` / `api/v1/datasets.py` / `schemas/rawdata.py` / `etl/introspect.py` / `tests/test_snapshot_service.py` |
| 003 | 自動鏡像 + DS 字典 COMMENT 轉換引擎(保留型別/comment 放寬) | done | ✓ | — | `backend/app/etl/mirror.py` / `etl/dictionary.py` / `tests/test_mirror.py` / `tests/test_dictionary.py` |
| 004 | 同步觸發端點 + worker task + sync_states 更新 | done | ✓ | 001,002,003 | `backend/app/api/v1/sync.py` / `api/v1/__init__.py` / `worker/tasks.py` / `services/sync_service.py` / `schemas/sync.py` / `tests/test_sync_api.py` |
| 005 | 前端 原始資料管理補強(移除查看欄位/schema 說明/過濾/時間欄/同步鈕) | done | ✓ | 002,004 | `frontend/src/components/datasets/DatasetBrowser.tsx` / `app/(main)/raw-data/page.tsx` / `app/(main)/etl-data/page.tsx` / `lib/api/datasetApi.ts` / `lib/api/syncApi.ts` / `constants/schemaDescriptions.ts` |
| 006 | 前端 排程友善 UI(下拉/時間選擇取代 cron 5 欄,預設全跑) | done | ✓ | — | `frontend/src/app/(main)/schedules/page.tsx` / `components/schedules/CronFriendlyPicker.tsx` / `utils/cron.ts` / `lib/api/scheduleApi.ts` |

## 拆解摘要

- **總數**:6 個 task,預估 ~18.5 hr;後端 4(001–004)、前端 2(005–006)。
- **起手可認領(無依賴)**:task-001、task-003、task-006(三者檔案不重疊,可同時開跑)。
- **依賴鏈**:
  - 後端資料/快照:`001 → 002`(002 用 001 的 model/repo)
  - 後端引擎:`003`(獨立,與 001/002 並行)
  - 後端同步整合:`001,002,003 → 004`(需 model + repo + mirror 引擎)
  - 前端:`002,004 → 005`(原始資料管理讀快照 + 同步鈕);`006` 獨立(既有排程 API)
- **並行性**:全 task `affected_files` **互不重疊** → 全部 `parallel: true`;僅 `api/v1/__init__.py` 由 task-004 獨占(v1.2 無他 task 動它),無同檔互鎖。
- **阻塞點**:001 為快照/同步鏈前置;004 需等 001+002+003 三者。
- **關鍵設計約束(避免同檔互鎖)**:
  1. **依賴鎖版集中 task-001**:`pyproject.toml` / `uv.lock` 只有 001 動(本版新增 `redis` 直用 client),其餘 task 不改。
  2. **`api/v1/__init__.py` 只屬 task-004**(掛 sync router);datasets router 已於起點註冊,002 不再動 `__init__.py`。
  3. **`etl/introspect.py` 只屬 task-002**;mirror 引擎(003)自帶型別內省,不碰 introspect.py。
  4. **既有 config-driven 引擎凍結**:`etl/{engine,reader,writer,comments}.py` 任何 task 不改(reader 的 `rds_database_url` 由 mirror/introspect **唯讀 import 重用**,不修改)。
- **In Scope 映射**:①→005 ②→005(etl-data)③→001,002 ④→002 ⑤→003 ⑥→003,004 ⑦→003(引擎放寬;design-base 規範更新走收口 `/reflect-rules`)⑧→006 ⑨業務資料名稱(GAT JOIN 快照落地)→001,002,005。
- **收口(全 task done 後由 orchestrator)**:小規模對 RDS 試跑(DS 幾張表 → hub 驗中文 COMMENT)→ `/scan-project` → comment 放寬走 `/reflect-rules` 記錄 → 全量同步由 user 確認後執行。

## 執行前置(orchestrator 提醒)

- **RDS 寫入屬對外不可逆動作**:task-003/004 的 Acceptance 以小規模(單/少數表)驗證;**全量 4747 表同步不在任何 task 內自動執行**,由 user 於收口確認後手動觸發。
- **comment 規範放寬**:與 v1.0/v1.1「每欄必帶繁中 Comment」底線衝突,屬設計規範調整,已於 propose 風險區註記;收口走 `/reflect-rules` 正式化,worker 實作時於 `fixed.md` 記錄。
