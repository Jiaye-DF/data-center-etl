---
id: task-008
title: 前端 排程管理 Dialog 化 + 固定全表增量 + 列表顯示行為/上次結果
status: done
parallel: true
depends_on: [task-006]
affected_files:
  - frontend/src/app/(main)/schedules/page.tsx
  - frontend/src/components/schedules/ScheduleFormDialog.tsx
  - frontend/src/lib/api/scheduleApi.ts
estimated_hours: 4
---

## 目標

排程管理**硬需求**:新增 / 編輯排程改用 **Dialog 彈窗**(頁面不再內嵌展開 `ScheduleForm`)。排程單一化為同步——表單**無逐表選擇**、固定「增量同步全部表」;列表「做什麼」欄一律顯示「增量同步全部表」,並顯示**上次執行結果**(task-006 API)。沿用本版彈窗風格(可擴充 `ConfirmDialog` 概念,獨立成 `ScheduleFormDialog` 避免動共用檔)。

## 設計要點

- 依賴 task-006:`scheduleApi` 回應加 `last_run_status` / `last_run_at`;`etl_table_uid` 恆 null。
- `lib/api/scheduleApi.ts`:
  - `Schedule` 介面加 `last_run_status: string | null`、`last_run_at: string | null`;`etl_table_uid` 保留(恆 null)。
  - `ScheduleCreatePayload` / `ScheduleUpdatePayload`:**停止傳送 `etl_table_uid`**(或固定 null);其餘不變。
- `components/schedules/ScheduleFormDialog.tsx`(新):
  - 遮罩 + 置中卡片(對齊 `ConfirmDialog`:Esc / 點遮罩 / 取消關閉),內含排程表單。
  - 欄位:名稱、`CronFriendlyPicker`(沿用,預設半夜 `DEFAULT_CRON_EXPR` = `0 3 * * *`)、描述、啟用。
  - **無逐表選擇**;顯示唯讀說明「此排程為增量同步全部來源表」。
  - `useCallback`/`memo` 對齊既有 handler 慣例;strict、禁 any。
- `app/(main)/schedules/page.tsx`:
  - **移除**頁面內嵌 `ScheduleForm`(改由 `ScheduleFormDialog` 承載)。
  - 「新增排程」按鈕 → 開 Dialog;每列「編輯」→ 開 Dialog 帶 initial。
  - 列表「執行範圍」欄改為「做什麼」:一律「增量同步全部表」。
  - 列表加「上次結果」欄:讀 `schedule.last_run_status`(以既有 `StatusBadge` 呈現 success/failed/未跑)+ `last_run_at`(`formatDateTime`)。
  - **既有「手動觸發」按鈕(現呼叫 `run_etl` trigger)改為觸發同步**:改呼叫既有同步端點(手動 = 同一個 `mirror_sync`,`trigger_type=manual`);taskiq 故障時的人工補灌走此路徑或原始資料頁「全量同步」鈕。若沿用 `runApi.triggerRun` 會落 `run_etl` → **不符單一化**,改用 `syncApi`(既有 `useTriggerSyncAllMutation` 或等價;若無對應則於本 task 內以既有 `/sync/all` mutation 串接)。保留刪除確認、啟停。

## Acceptance

- [x] `cd frontend && npm run typecheck && npm run lint` green(strict,禁 any)
- [x] `npm run build` 成功
- [x] 頁面實測:點「新增排程」開**彈窗**(頁面不再內嵌展開表單);表單**無逐表選擇**,送出後 `etl_table_uid` 為 null;預設 cron 為半夜 `0 3 * * *`
- [x] 編輯既有排程於 **Dialog** 進行;列表「做什麼」欄顯示「增量同步全部表」,「上次結果」欄顯示 success/failed/未跑 + 時間
- [x] 「手動觸發」按鈕觸發的是**同步**(mirror_sync)而非 `run_etl`(檢視 network 呼叫 `/sync/*` 而非 `/runs` trigger)
- [x] `grep -n "ScheduleFormDialog" frontend/src/app/\(main\)/schedules/page.tsx` 有輸出且頁面不再內嵌 `<form>` 展開(以 Dialog 承載)

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
- `docs/Design-Base/00-overview/05-timezone.md`
