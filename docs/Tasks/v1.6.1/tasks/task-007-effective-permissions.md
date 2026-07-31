---
id: task-007
title: 預覽端點 effective-permissions(聯集 ∩ 範圍,default-closed,走快取)
status: done
parallel: true
depends_on: [task-002, task-003]
affected_files:
  - backend/app/services/effective_permission_service.py
  - backend/app/api/v1/api_clients.py
  - backend/app/schemas/client_setting_preview.py
  - backend/tests/test_effective_permissions.py
estimated_hours: 3
model: opus
effort: high
---

## 目標

`GET /api/v1/api-clients/{uid}/effective-permissions`(admin 專用):計算單一 API Client 的最終可見欄位——**Role 設定檔 ∪ 特例(過濾已過期)**,逐作業取「授權 ∩ 作業範圍」,輸出 `{作業: {表: {欄位: read/edit}}}`;讀取走 task-003 快取。**此計算語意即模組③ 的展開語意,獨立 service 供後續沿用。**

## 實作要點

- 計算規則(對齊 Arch「三情境對照」):
  - 無 Role 且無特例 → 空結構;作業有綁但無表欄位授權 → 該作業空物件(**default-closed**;作業開門、授權給欄位,缺一不可)。
  - 授權項超出作業範圍的部分不生效(∩ 上限);`*` 展開為作業範圍內該表全欄位;`edit` 隱含 `read`,同欄位取較高動作。
  - 特例 `expires_at` < now(naive UTC+8)一律排除;NULL 不設限。
- 快取 key `client_setting:effective:<client_uid>`;測試直接以 repo 塞資料建構情境(不依賴 004–006 端點)。
- client 不存在 / 已軟刪 → 404;回應統一封套。

## Acceptance

- [ ] `uv run pytest tests/test_effective_permissions.py` 全綠(Arch 範例情境:P1 於 O1 授 C11/C21(edit)/C31 → 預覽等價 `{O1: {T1:{C11:read}, T2:{C21:edit}, T3:{C31:read}}}`;default-closed;過期特例排除 / 未過期納入;無 Role 無特例回空;超範圍授權不生效;`*` 展開;第二次讀取命中快取)
- [ ] 非 admin 403、不存在 client 404
- [ ] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/06-timezone.md`
