---
id: task-009
title: 端到端收口驗證 — 樣本表複核鏈路 + 對外承諾覆核 + 驗證紀錄
status: pending
parallel: false
depends_on: [task-002, task-004, task-005, task-006, task-007, task-008]
estimated_hours: 2
affected_files:
  - docs/Tasks/v1.5.0/verification-v1.5.0.md
---

## 目標

以 1–2 張樣本表(建議 `GEN_FILE` 員工/`GEM_FILE` 部門)走完「draft→confirmed→JSON 英文 key→view 查詢」全鏈路,覆核 propose 對外承諾,產出驗證紀錄(對齊 v1.4.1 `verification-v1.4.1.md` 前例;Playwright 依 `05-CI/06-e2e.md` 預設 disabled,以機械化手測清單代替)。**全量複核不在本版**(user 決議)。

## 內容(手測清單,逐條記錄實測結果)

1. `docker compose up -d --build` 全服務 healthy。
2. 草稿匯入:`uv run python scripts/seed_semantic_mappings.py` → RDS `semantic_mappings` 筆數 = 12,280(333 表層級 + 11,947 欄)。
3. 樣本複核:`--confirm-table GEN_FILE` → 該表全列 confirmed。
4. 觸發 ETL 同步 → 自有 DB 副本與 RDS 一致(筆數/抽樣列比對);轉換 cache 已失效。
5. JSON API:`GET .../tables/M2201/GEN_FILE/rows` 回傳 key 為英文名、無 `gen01` 類魔術 key、draft 欄位不出現;未複核表回 404。
6. view:目標 RDS 存在 `m2201_en.employees`(或對應英文表名)且 `SELECT * LIMIT 1` 欄名為英文;mapping 更新後重生 view 定義同步。
7. comment 覆核(B1/B3;若 DMS 已加 `GAE_FILE`):同步後 comment 缺漏欄數 ≤65(`verify` SQL 統計);未加表則記錄「B1 待 DMS 前置」不擋收口。
8. 模組分類:資料集頁按模組篩選正常(task-008 手測 case 重跑)。
9. 後端 `uv run pytest` / ruff / mypy、前端 lint / typecheck / build 全綠。

## Acceptance

- [ ] `[ -f docs/Tasks/v1.5.0/verification-v1.5.0.md ]` 且逐條含實測結果(指令 + 輸出摘要),無「未執行」空條目
- [ ] 上列 2/3/4/5/6 全數通過(7 允許記錄前置未成;8/9 全綠)
- [ ] 對外承諾四條逐一覆核並在驗證紀錄標注 ✅/⚠️(⚠️ 需附原因與後續)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/99-code-review/00-overview.md`
- `docs/Design-Base/99-code-review/03-pr-self-check.md`
- `docs/Design-Base/05-CI/06-e2e.md`
