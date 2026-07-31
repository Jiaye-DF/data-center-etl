---
id: task-011
title: e2e 收口 + 稽核驗證 + verification 文件 + Arch 回寫
status: pending
parallel: false
depends_on: [task-001, task-002, task-003, task-004, task-005, task-006, task-007, task-008, task-009, task-010]
affected_files:
  - docs/Tasks/v1.6.1/verification-v1.6.1.md
  - docs/Arch/datahub-api-gateway-arch.html
estimated_hours: 3
model: sonnet
effort: medium
---

## 目標

依 propose 驗收標準逐條 e2e 驗證並落 `verification-v1.6.1.md`;實作與 Arch 文件的偏離回寫 `datahub-api-gateway-arch.html`(模組② 狀態與細節)。

## 實作要點

- 逐條走 propose「驗收標準」:建表驗證(11 表 / NOT NULL / 另連線直讀 `client_setting.*`)、Arch 範例整合流程、default-closed、特例過期、防呆 4xx、快取三情境(命中 / 失效 / 降級)、無 Role 無特例回空、迴歸(v1.6.0 全測試綠)、前端手測截圖。
- 稽核驗證:系統別 / 作業 / 設定檔 / Role / 指派 / 特例寫操作各抽一筆確認 audit_logs 有事件且 detail 無機密。
- Arch 回寫:模組② 標記落地狀態、`client_setting` schema 落點、快取層歸屬(拆解註記的 key 前綴 / TTL);偏離逐項列明。
- 殘留事項(如 UI 人工複測、RDS 正式環境建表)列入 verification 殘留節。

## Acceptance

- [ ] `docs/Tasks/v1.6.1/verification-v1.6.1.md` 存在且逐條對應 propose 驗收標準(附指令輸出 / 截圖引用)
- [ ] `cd backend && uv run pytest` 全綠;`uv run ruff check app tests` + `uv run mypy app` 無新增錯誤;`npm run lint` + `npm run typecheck` 乾淨
- [ ] `docs/Arch/datahub-api-gateway-arch.html` 模組② 已回寫且與實作一致(偏離零遺漏)

## 必讀檔(Just-in-time)

- `docs/Design-Base/99-code-review/00-overview.md`
- `docs/Design-Base/99-code-review/03-pr-self-check.md`
- `docs/Design-Base/03-backend/07-testing.md`
