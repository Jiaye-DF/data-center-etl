---
id: task-006
title: 前端語意映射管理頁 + sidebar 獨立入口
status: done
parallel: false
depends_on: [task-004, task-005]
affected_files:
  - frontend/src/lib/api/semanticMappingApi.ts
  - frontend/src/app/(main)/semantic-mappings/page.tsx
  - frontend/src/components/semantic/SemanticMappingManager.tsx
  - frontend/src/components/layout/Sidebar.tsx
estimated_hours: 4
---

## 目標

新增「語意映射管理」頁(admin-only),sidebar **獨立入口 / 分組**(user 明示:不併入「ETL 作業」的 ETL 資料管理區塊):瀏覽 / 篩選 / 編輯映射、轉態、觸發「同步 view」。

## 內容

- `semanticMappingApi.ts`(RTK Query):list / tables / patch / confirm-table / sync-views 五端點,tag 失效串好(patch / confirm / sync 後列表重抓)。
- 頁面 `/semantic-mappings`:
  - 表名下拉(含 draft/confirmed 計數)+ 狀態篩選(全部/draft/confirmed)+ 關鍵字搜尋 + 分頁(對齊 `/sources` 頁既有篩選視覺語言)。
  - 列表欄:表名 / 欄名 / 英文名 / 中文名 / 狀態 / 更新時間;列內編輯英文名、中文名(送 PATCH),狀態切換 draft ↔ confirmed。
  - 「整表轉 confirmed」與「同步 view」按鈕(皆 ConfirmDialog 確認;sync 完成顯示重生結果訊息)。
- Sidebar:新分組「語意層」(或同級獨立分組)含「語意映射管理」入口;**不**放進「ETL 作業」分組。
- 日期時間走 `utils/datetime.ts`;無 `any`;共用元件優先(`ConfirmDialog` / `Pagination` / `AutoRefreshControl` 視需要)。

## Acceptance

- [ ] `cd frontend && npm run typecheck && npm run lint` 全綠
- [ ] `grep -n "semantic-mappings" frontend/src/components/layout/Sidebar.tsx` 有獨立分組入口(不在「ETL 作業」分組 items 內)
- [ ] `docker compose up -d --build` 後手測:篩選 draft → 編輯英文名 → 轉 confirmed → 按「同步 view」→ 成功訊息含重生統計;member 帳號看不到入口
- [ ] 手機寬度(390px)列表可橫向捲動,無版面破版(`02-frontend/06-rwd.md`)

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/01-routing-and-error.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/04-datetime.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
