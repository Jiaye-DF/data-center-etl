---
id: task-003
title: 同步收尾掛接:autofill → 副本重灌 → view 重生同輪生效
status: pending
parallel: false
depends_on: [task-002]
affected_files:
  - backend/app/worker/tasks.py
  - backend/tests/test_semantic_mapping_sync.py
estimated_hours: 2
---

## 目標

`mirror_sync` 收尾在既有 `refresh_semantic_copy_and_views` **之前**呼叫 task-002 的 autofill,使自動補的 confirmed 列於同一輪被重灌進副本、觸發簽名變更而重生 view,同步結束即全鏈生效。

## 內容

- 掛點:`backend/app/worker/tasks.py` `mirror_sync` 收尾段(現行呼叫 `refresh_semantic_copy_and_views` 處),順序:autofill(寫 RDS 真身)→ 副本重灌 → view 重生;autofill 統計進 run log(對齊既有收尾 log 慣例)。
- Graceful 語意對齊既有:RDS `erp_metadata.semantic_mappings` 不存在 → 略過 autofill 不 fail run;autofill 本身失敗 → log warning 後仍執行既有副本重灌流程(不因補列失敗擋住原有收尾)。
- 手動 `POST /semantic-mappings/sync-views`(`semantic_apply`)**不**掛 autofill(僅同步路徑觸發;管理頁按鈕語意維持「套用人工異動」不變)。
- 增量 / 手動全量兩模式收尾同一路徑,無需分流。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_semantic_mapping_sync.py` 全綠,含新測試:(a) 收尾順序 autofill 先於 replace_all(mock 呼叫序斷言);(b) semantic_mappings 不存在 → 略過不 fail;(c) autofill 拋例外 → warning 後副本重灌照跑;(d) `semantic_apply` 路徑無 autofill 呼叫
- [ ] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤
- [ ] `grep -n "semantic_autofill" backend/app/worker/tasks.py` 僅出現在 mirror_sync 收尾路徑

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/07-testing.md`

## 派工建議

- model:opus / effort:medium(掛接為主,惟 worker 收尾為全系統要害檔)
