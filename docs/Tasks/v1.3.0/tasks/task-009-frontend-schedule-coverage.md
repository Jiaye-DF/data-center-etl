---
id: task-009
title: 前端 依表檢視頁(schema 分頁 + 表清單 + 排程/結果/下次執行 + 篩選)
status: pending
parallel: true
depends_on: [task-007]
affected_files:
  - frontend/src/app/(main)/schedules/coverage/page.tsx
  - frontend/src/components/schedules/ScheduleCoverageBrowser.tsx
  - frontend/src/lib/api/scheduleCoverageApi.ts
  - frontend/src/utils/cron.ts
  - frontend/src/components/layout/Sidebar.tsx
estimated_hours: 4
---

## 目標

「排程管理依表檢視」頁:UI 參照原始資料管理(schema 分頁籤 + 表清單瀏覽器),但**欄位聚焦排程 / 執行狀態**——資料表(代碼)、業務資料表名稱、納入排程(預設已納入;**可逐表排除 / 納入**)、套用排程(cron 摘要如「每天 03:00」)、上次同步時間、上次結果、下次執行(前端由 cron 推算)。可篩「未被涵蓋的表」(被排除 / 無排程)。走**新路由 `/schedules/coverage`**,不動 task-008 的排程列表頁。

## 設計要點

- 依賴 task-007 coverage API(`/schedule-coverage/schemas`、`/schedule-coverage/tables`、`PATCH /schedule-coverage/exclusion`)。
- `lib/api/scheduleCoverageApi.ts`(新):`useListCoverageSchemasQuery` / `useListCoverageTablesQuery`(params: schema/page/pageSize/included/lastResult/keyword)+ `useSetExclusionMutation`(body schema/table/excluded,`invalidatesTags` 使清單重讀);型別對齊後端 `CoverageTableItem`(含 `included` / `excluded`)。
- `utils/cron.ts`:**加**下次執行推算 `nextRunAt(cronExpr: string, from?: Date): Date | null`——僅支援本專案三型(daily/weekly/monthly,沿用 `fromCron`);無法解析回 null。純函式、UTC+8 語意(對齊既有 friendly 工具)。**只本 task 動此檔**。
- `components/schedules/ScheduleCoverageBrowser.tsx`(新):schema 分頁籤 + 表清單表格;欄位如上;`included`/`excluded` 以膠囊(已納入 / 已排除 / 無排程)呈現;每列加**「排除 / 納入」按鈕**(admin only,呼叫 `useSetExclusionMutation`,樂觀或重讀);`applied_cron` 以 `describeFriendly(fromCron(...))` 顯示摘要,被排除者下次執行顯示「—」;`nextRunAt` 顯示下次執行;上次結果以既有 `StatusBadge` 風格。篩選列:納入狀態(全部 / 已納入 / 未涵蓋)/ 上次結果 / 關鍵字。RWD、字級 ≥14px、`memo`/`useCallback` 對齊既有瀏覽器元件。
- `app/(main)/schedules/coverage/page.tsx`(新):載入 schema 清單 → 分頁籤 → `ScheduleCoverageBrowser`;頂部提示「每張來源表預設納入夜間增量排程」+「涵蓋缺口:N(被排除 M / 無排程 K)」;連回 `/schedules` 的 Link。
- `components/layout/Sidebar.tsx`:排程管理下加「依表檢視」導覽項(指向 `/schedules/coverage`);僅新增一項,不動既有項排列邏輯。

## Acceptance

- [ ] `cd frontend && npm run typecheck && npm run lint` green(strict,禁 any)
- [ ] `npm run build` 成功
- [ ] `utils/cron.ts` 可驗:`nextRunAt('0 3 * * *', new Date('2026-07-06T05:00:00+08:00'))` 回次日 03:00(UTC+8);無法解析的 cron(如 `*/5 * * * *`)回 `null`(vitest/jest 或 build 前 tsx 斷言;無框架則 PR 附 REPL)
- [ ] 頁面實測:`/schedules/coverage` 顯示 schema 分頁 + 表清單;有啟用排程且無人排除時每張表「已納入」、缺口 0;套用排程顯示「每天 03:00」、下次執行有值
- [ ] 逐表排除實測:點某表「排除」→ 該列變「已排除」、缺口 +1、下次執行「—」;點「納入」還原;「未涵蓋」篩選列出被排除表
- [ ] Sidebar 出現「依表檢視」導覽項且可進入該頁

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/04-datetime.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
- `docs/Design-Base/00-overview/05-timezone.md`
