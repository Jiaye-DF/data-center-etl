---
id: task-007
title: e2e 驗證 + 收口文件
status: pending
parallel: false
depends_on: [task-001, task-002, task-003, task-004, task-005, task-006]
affected_files:
  - docs/Tasks/v1.5.1/verification-v1.5.1.md
estimated_hours: 2
---

## 目標

對 propose v1.5.1 驗收標準逐條實測(真實 RDS + docker compose 環境),產出 `verification-v1.5.1.md` 佐證,supporting 收口(scan / reflect / merge)。

## 內容

- 逐條驗 propose「驗收標準」與各 task Acceptance 的整合面:
  1. 快照同步(source / target)進度條全程顯示至完成。
  2. 管理頁:編輯 → 轉 confirmed → 同步 view → RDS 查得 `<schema>_view` 新 view;`_en` 無新增物件。
  3. TSV 與 RDS draft 查無 `unused` 開頭英文名;BMA_FILE confirmed 列未變。
  4. 後端 `uv run pytest tests -q` 全綠;前端 `npm run typecheck` + `npm run lint` 全綠。
- 文件記錄:執行環境、命令輸出摘要、RDS 查證 SQL 與結果、殘留事項(人工移除清單狀態)。

## Acceptance

- [ ] `[ -f docs/Tasks/v1.5.1/verification-v1.5.1.md ]` 且逐條對映 propose 驗收標準(含實測輸出摘要)
- [ ] 後端完整套件 + 前端 typecheck/lint 全綠的輸出證據記錄在案
- [ ] RDS 實測 SQL(查 `_view` schema view 清單 / 查 unused 命名筆數 = 0)與結果貼附

## 必讀檔(Just-in-time)

- `docs/Design-Base/99-code-review/00-overview.md`
- `docs/Design-Base/99-code-review/03-pr-self-check.md`
