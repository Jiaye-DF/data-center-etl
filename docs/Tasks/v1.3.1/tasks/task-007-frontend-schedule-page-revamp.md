---
id: task-007
title: 前端排程管理頁改版(逐表瀏覽器 + 進階篩選 + 批次啟停 + 編輯 Dialog)+ scheduleApi 重構
status: pending
parallel: true
depends_on: [task-004]
affected_files:
  - frontend/src/app/(main)/schedules/page.tsx
  - frontend/src/components/schedules/ScheduleTableBrowser.tsx
  - frontend/src/components/schedules/ScheduleFormDialog.tsx
  - frontend/src/lib/api/scheduleApi.ts
estimated_hours: 4
---

## 目標

把 `/schedules` 改為與 `/sources`、`/sources-hub` **同一套視覺語言**(schema 分頁籤 + 表清單瀏覽器 + 可摺疊進階篩選 + 分頁)的**逐表檢視**:逐表看啟用/排程時間/上次同步/上次結果/下次執行,編輯走 Dialog,批次啟停,**移除「新增排程」按鈕**(排程由系統自動建)。

## 內容

- 先 Read `components/datasets/DatasetBrowser.tsx`(schema 分頁 + 表清單 + 進階篩選版型基準)、`app/(main)/sources/page.tsx`、`components/schedules/ScheduleFormDialog.tsx`(v1.3.0 既有,改為 edit-only)、`utils/cron.ts`(`nextRunFromCron`/`describeCron` 沿用)、`utils/datetime.ts`。
- `lib/api/scheduleApi.ts`:型別改逐表視角(對齊 task-004 response:`table_name`/`business_name`/`schedule_uid`/`cron_expr`/`is_enabled`/`last_synced_at`/`last_run_status`);endpoints 改 `listScheduleTables`(schema+分頁+篩選)、`getScheduleSchemas`、`updateSchedule`(cron/啟停/描述)、`setScheduleEnabled`、`batchSetEnabled`;**移除** create/delete。
- `components/schedules/ScheduleTableBrowser.tsx`(新):schema 分頁籤 + 表清單 table(欄位:資料表 / 業務名 / 啟用 toggle(admin)/ 排程時間(`describeCron`)/ 上次同步 / 上次結果(StatusBadge)/ 下次執行(`nextRunFromCron`,停用顯「—」))+ 可摺疊進階篩選(schema / 啟用狀態 / 上次結果 / 關鍵字)+ 分頁 + 「**全部啟用**」按鈕與「符合篩選批量啟用/停用」(Dialog 確認 + 影響筆數,admin only)。
- `components/schedules/ScheduleFormDialog.tsx`:改為 edit-only(點某表排程時間 → Dialog 改 cron/啟停/描述);移除新增模式與「建立後立即啟用」。
- `app/(main)/schedules/page.tsx`:改為渲染 `<ScheduleTableBrowser />`(移除 v1.3.0 的內嵌清單、`useListEtlTablesQuery`/etlConfigApi 引用、手動觸發、新增排程按鈕)。

## Acceptance

- [ ] `cd frontend && npm run typecheck` 零錯誤
- [ ] `cd frontend && npm run lint` 零警告零錯誤（`--max-warnings=0`）
- [ ] `cd frontend && npm run build` 成功
- [ ] `grep -rn "etlConfigApi\|useListEtlTablesQuery\|createSchedule\|deleteSchedule" frontend/src/app/(main)/schedules frontend/src/components/schedules frontend/src/lib/api/scheduleApi.ts` 無命中
- [ ] `/schedules` 頁碼結構:schema 分頁籤 + 表清單 + 進階篩選 + 「全部啟用」按鈕(可由 build 後 grep 元件字串佐證)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/04-datetime.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
