---
id: task-006
title: 自動刷新前端 — AutoRefreshControl 共用元件 + 各檢視輪詢 + 觸發 404 修復
status: done
parallel: false
depends_on: [task-005]
affected_files:
  - frontend/src/components/common/AutoRefreshControl.tsx
  - frontend/src/lib/api/runApi.ts
  - frontend/src/app/(main)/runs/page.tsx
  - frontend/src/app/(main)/runs/[uid]/page.tsx
  - frontend/src/components/runs/RunLogTable.tsx
  - frontend/src/components/datasets/DatasetBrowser.tsx
  - frontend/src/app/(main)/page.tsx
estimated_hours: 3.5
model: sonnet
effort: high
---

## 目標

AWS 主控台式的重新整理體驗(純 UI 層,不改任何 API):非同步狀態檢視自動輪詢 + 統一的「手動重新整理鈕 + 自動更新狀態 + 最後更新時間」控制元件;run 結束即停輪詢。順修 runs 頁手動觸發按鈕 404。

## 實作要點

1. **共用元件** `components/common/AutoRefreshControl.tsx`(reuse 必抽,對齊 `05-components.md`):props = `onRefresh`(手動 refetch)、`isFetching`、`lastUpdatedAt`、`polling: boolean`;呈現:重新整理 icon 鈕(轉圈 = isFetching)+「自動更新中(Ns)/ 已暫停」字樣 +「最後更新 HH:mm:ss」(`utils/datetime.ts` 格式化)。觸控目標 ≥ 44px。
2. **觸發 404 修復**(`runs/page.tsx` + `runApi.ts`):按鈕改走 `syncApi.useSyncAllMutation`(`POST /sync/all`,202);`runApi.ts` 移除已死的 `triggerRun`(`POST /runs/trigger` 端點 v1.3.1 已移除)及其匯出;成功訊息沿用、失敗訊息真實反映錯誤。**勿動 005 加的 getActiveRun。**
3. **各檢視輪詢**(RTK Query `pollingInterval` + `skipPollingIfUnfocused`,間隔:執行狀態類 5s、清單/儀表板 30s):
   - runs 清單(已有 10s):掛 AutoRefreshControl(顯示 + 手動 refetch)。
   - run 明細 + `RunLogTable`:run `status === 'running'` 時 5s 輪詢(summary + logs),結束即停(`pollingInterval: 0`);掛 AutoRefreshControl。
   - `DatasetBrowser`(原始 / ETL 資料清單):30s 輪詢 + AutoRefreshControl(放 header 按鈕列旁,不與既有確認框動線打架)。
   - 總覽儀表板 `(main)/page.tsx`:30s 輪詢 + AutoRefreshControl。
4. 輪詢一律視窗未聚焦即暫停;**不**改後端、**不**加新端點。

## Acceptance

- [x] `npm run typecheck` 通過;`npm run lint`(--max-warnings=0)通過
- [x] `[ -f frontend/src/components/common/AutoRefreshControl.tsx ]` 為真
- [x] `grep -rn "runs/trigger" frontend/src` 無輸出(死端點呼叫清除)
- [ ] `docker compose up -d --build frontend` 後手測:runs 頁「手動觸發(全部啟用表)」回 202 且新 run 出現在清單(無 404);執行中 run 明細逐表 log 自動增加、run 結束後網路面板不再輪詢;資料清單 / 儀表板顯示「最後更新」並可手動刷新 — **待 orchestrator 手測**
- [x] 四個掛載點(runs 清單 / run 明細 / 資料清單 / 儀表板)皆使用同一 AutoRefreshControl 元件(無複製貼上變體)

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/04-datetime.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
