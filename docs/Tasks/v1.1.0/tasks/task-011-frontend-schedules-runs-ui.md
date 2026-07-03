---
id: task-011
title: 前端排程管理 + 執行紀錄 / 逐表詳細 log 頁
status: done
parallel: true
depends_on: [task-005, task-009]
affected_files:
  - frontend/src/app/(main)/schedules/page.tsx
  - frontend/src/app/(main)/runs/page.tsx
  - frontend/src/app/(main)/runs/[uid]/page.tsx
  - frontend/src/lib/api/scheduleApi.ts
  - frontend/src/lib/api/runApi.ts
  - frontend/src/components/runs/RunLogTable.tsx
estimated_hours: 4
---

## 目標

排程管理頁(CRUD + 啟停 + 手動觸發按鈕)與執行紀錄頁:run 清單(狀態 / 觸發方式 / 起訖)、單 run 明細頁顯示**逐表詳細 log**(表名 / 讀寫筆數 / 耗時 / 狀態 / 錯誤明細含 stack trace 展開)。

## 範圍要點

- 串 task-005 API;run 清單與 log 支援狀態過濾與分頁。
- 手動觸發後即時反映新 run(RTK Query invalidate)。
- 錯誤明細(stack trace)預設收合、點擊展開;失敗表列醒目標示。
- viewer 角色:排程寫入與手動觸發控件隱藏或 disabled。
- 時間顯示 UTC+8 走 `utils/datetime.ts`;**不改** `(main)/layout.tsx`。

## Acceptance

- [x] `cd frontend && npm run lint && npx tsc --noEmit` 全綠
- [x] `cd frontend && npm run build` 成功
- [x] `! git diff --name-only | grep -q "app/(main)/layout.tsx"` 成立(未動 layout)
- [x] 手測 case(記錄於 task 完成註記):建排程、啟停、手動觸發出現新 run、run 明細逐表 log 欄位齊全、失敗 run 可展開 stack trace

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/04-datetime.md` + `docs/Design-Base/00-overview/05-timezone.md`
- `docs/Design-Base/02-frontend/05-components.md`

## 完成註記(2026-07-03,worker: claude-E)

- **交付**:`scheduleApi.ts`(list / create / update / delete / enable / disable,tag `Schedule`)、`runApi.ts`(list / detail / logs / trigger,tag `Run` / `RunLog`,trigger 成功 invalidate run 清單即時反映)、`schedules/page.tsx`(CRUD 表單 + 啟停 + 逐排程手動觸發 + 兩段式刪除確認)、`runs/page.tsx`(狀態 / 觸發方式過濾 + 分頁 + 10s 輪詢 + 手動觸發全部啟用表)、`runs/[uid]/page.tsx`(run 摘要 + 逐表 log)、`RunLogTable.tsx`(逐表 log 表格 + 狀態過濾 + 分頁 + stack trace 預設收合點擊展開 + 失敗列紅底醒目;並 export 共用 `Pagination` / `StatusBadge` / `TRIGGER_TYPE_LABELS` / `formatNullableDateTime`,見 fixed.md §17)。viewer 角色隱藏新增 / 操作欄 / 觸發按鈕(`useAuth().isAdmin`);時間顯示走 `utils/datetime.ts`;未動 `(main)/layout.tsx`。
- **手測記錄**(本機 compose 全棧 healthy;瀏覽器自動化因多瀏覽器連線需人工選擇無法在無人值守環境使用,改以「UI 實際呼叫的同一組 API 依 UI 操作順序實跑」+ dev server 頁面 SSR 驗證):
  1. 建排程:`POST /schedules`(name/cron/全部啟用表/描述)→ 201,清單可見;非法 cron 回 400 `detail`(表單以 `extractApiErrorDetail` 呈現同訊息)。
  2. 啟停:`POST /schedules/{uid}/disable` → `is_enabled=false`;`/enable` → `true`;`PATCH` 更新 name/cron 成功。
  3. 手動觸發:`POST /runs/trigger`(etl_table_uid=null)→ `task_id` 回傳、`run_uid=null`(佇列模式,符合 fixed.md §15);數秒後 `GET /runs` 出現新 run(manual / failed / total_tables=4)— UI 端由 mutation invalidate `Run:LIST` 觸發同一查詢 refetch。
  4. run 明細逐表 log:`GET /runs/{uid}` 摘要欄位齊全;`GET /runs/{uid}/logs` 每列含 source_schema.source_table / status / row_count / duration_ms / started_at / finished_at / error_message / error_stack(完整 Python traceback);`?status=failed` 過濾正確(4/4)。
  5. 失敗 stack trace:本機無 SOURCE_DB_* env,4 表皆失敗且 `error_stack` 非空(RunLogTable 失敗列紅底、stack 預設收合、按鈕展開 `<pre>` 呈現)。
  6. 頁面驗證:dev server 下 `/schedules`、`/runs`、`/runs/{uid}` 無 cookie 一律 307 → `/login`(middleware guard);帶登入 cookie 皆 200 且 SSR 初始畫面正常,無編譯 / runtime 錯誤。測試排程已於手測後刪除(軟刪除)。
- **附帶**:compose 內 `etl_backend` / `etl_frontend` image 為舊碼,已重 build 並確認全服務 healthy(未動 compose 檔);發現後端 `created_at`(UTC)與 `started_at`(+8)時區混用,記 fixed.md §18(非本 task 引入、白名單外不修)。
