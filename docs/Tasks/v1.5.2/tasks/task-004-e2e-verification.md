---
id: task-004
title: e2e 驗證 + 收口文件
status: done
parallel: false
depends_on: [task-001, task-002, task-003]
affected_files:
  - docs/Tasks/v1.5.2/verification-v1.5.2.md
estimated_hours: 2
---

## 目標

以真實(或測試)RDS 走 propose 驗收標準全項,產出 `verification-v1.5.2.md` 收口文件。

## 內容

- `docker compose up -d --build` 啟動後執行(**禁** start-dev):
  1. 來源測試表加一欄 → 觸發同步 → 目標表出現該欄且資料進入(task-001 承諾)。
  2. `erp_metadata.semantic_mappings` 出現 confirmed 列:english=小寫原欄名、zh=字典值或空、updated_by=全零 UUID(task-002 承諾)。
  3. 同輪結束後:該表語意 view 含新欄位;`/api/v1/data` JSON 查詢回應含新 key(task-003 承諾)。
  4. 既有映射列不覆寫:抽 BMA_FILE confirmed 樣本,自動補列前後 diff 為空。
  5. 手測:管理頁把自動列英文名改正式名 → 「同步 view」→ view 欄名更新(42P16 重建路徑正常)。
- 逐項記錄命令 / 回應摘要 / 截圖說明進 `verification-v1.5.2.md`(格式比照 `docs/Tasks/v1.5.1/verification-v1.5.1.md`);任何一項 fail → 回報對應 task 修正,不標 done。

## Acceptance

- [x] `cd backend && uv run pytest` 全套全綠(339 passed);`uv run ruff check app tests` 無錯誤;`uv run mypy app` 僅既有 `schedule_repo.py:528` 一筆(非本版新增)
- [x] `docs/Tasks/v1.5.2/verification-v1.5.2.md` 存在,且上列 1–5 每項有結果記錄(pass/fail + 證據)
- [x] 驗證期間 run log 無新增 ERROR 級訊息(`docker compose logs backend worker` 抽查)

## 必讀檔(Just-in-time)

- `docs/Design-Base/99-code-review/00-overview.md`
- `docs/Design-Base/99-code-review/03-pr-self-check.md`
- `docs/Design-Base/03-backend/07-testing.md`

## 派工建議

- model:sonnet / effort:medium(執行驗證與記錄為主)
