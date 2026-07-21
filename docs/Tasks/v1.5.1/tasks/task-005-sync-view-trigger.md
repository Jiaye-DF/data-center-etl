---
id: task-005
title: 「同步 view」觸發端點(副本重灌 + view 重生共用化)
status: done
parallel: false
depends_on: [task-004]
affected_files:
  - backend/app/worker/tasks.py
  - backend/app/api/v1/semantic_mappings.py
  - backend/app/services/semantic_admin_service.py
  - backend/tests/test_semantic_mappings_api.py
  - backend/app/etl/view_generator.py
  - backend/app/schemas/semantic_mapping.py
estimated_hours: 3
---

## 目標

管理頁的映射異動可**即時生效**:把 `mirror_sync` 收尾的「語意映射副本重灌 + view 重生」邏輯抽成可共用函式,新增手動觸發端點,不必等下一輪 ETL 同步。

## 內容

- 從 `worker/tasks.py` 收尾段抽出共用 async 函式(副本 `replace_all` + 失效 `semantic-mappings` 快取 + `regenerate_views_if_changed`),`mirror_sync` 與新端點共用同一實作;graceful 語意不變(來源表不存在 → 略過)。
- 新端點 `POST /semantic-mappings/sync-views`(admin):執行上述共用函式,回報副本筆數與 view 重生結果(建立數 / 失敗表數)。
- 端點為同步執行(小表 + view 重生秒級,免進 worker 佇列);逾時與錯誤依既有 exception handler 慣例回 ApiResponse。
- 注意 task-002 改名後落點為 `<schema>_view`(若 002 尚未完成,本 task 不動後綴,僅共用化)。

## Acceptance

- [x] `cd backend && uv run pytest tests/test_semantic_mappings_api.py tests/test_semantic_mapping_sync.py tests/test_view_generator.py` 全綠(含:sync-views 端點觸發後副本更新、mirror_sync 行為不變)
- [x] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤
- [x] `grep -n "sync-views" backend/app/api/v1/semantic_mappings.py` 有端點定義;`worker/tasks.py` 收尾段改呼叫共用函式(無重複實作)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
