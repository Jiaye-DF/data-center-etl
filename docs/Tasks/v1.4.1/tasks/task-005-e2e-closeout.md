---
id: task-005
title: 端到端收口驗證 — 全流程手測清單 + 對外承諾逐條覆核 + 驗證紀錄
status: done
parallel: false
depends_on: [task-004]
affected_files:
  - docs/Tasks/v1.4.1/verification-v1.4.1.md
estimated_hours: 1.5
---

## 目標

以 `docker compose up -d --build` 完整環境逐條覆核 propose「對外承諾」與「驗收標準」,產出驗證紀錄檔(跨 area 三段鏈之 e2e 段;本專案 Playwright 預設 disabled — `05-CI/06-e2e.md`,以機械化手測清單代替,對齊 v1.4.0 前例)。

## 規格

執行下列驗證並將每條結果(命令 + 輸出摘要 + pass/fail)記入 `verification-v1.4.1.md`:

1. **migration 後狀態**(SQL):`roles` 表存在且 `admin` / `viewer` 兩筆 seed;既有 `users` 全數帶關聯角色(無 NULL);`users.role` 舊欄位 + `ck_users_role` 原樣保留
2. **對外值零變化**:admin / viewer 各一,`curl /api/v1/auth/me` 之 `role` 欄位名與值與 v1.4.0 一致
3. **授權行為零變化**:viewer 呼叫寫入類 API 403;admin 2xx;SSO 首次登入為 viewer(測試涵蓋即可,引 pytest 結果)
4. **指派即時生效**:UI 將某使用者 viewer ↔ admin 互換,重新整理後權限即時反映;`audit_logs` 可查到 `role_assigned`
5. **全套迴歸**:`cd backend && uv run pytest` 全綠;`cd frontend && npm run typecheck && npm run lint && npm run build` 全綠
6. **無 DROP**:本版新增 migration 無任何 DROP(`grep -i -E "drop_table|drop_column|DROP TABLE|DROP COLUMN" backend/alembic/versions/v7_add_v141_roles.py` 無輸出)
7. **人工移除清單**:`docs/Tasks/v1.4.1/manual-removal-checklist.md` 存在且列 `users.role` + `ck_users_role`

任一 fail → 不標 done,回報 orchestrator 開補洞 task(或寫 `fixed.md`)。

## Acceptance

- [ ] `[ -f docs/Tasks/v1.4.1/verification-v1.4.1.md ]` 且上述 7 項逐條有結果紀錄、全數 pass
- [ ] `docker compose up -d --build` 起站後所有容器 healthy(`docker compose ps` 無 unhealthy / restarting)
- [ ] `cd backend && uv run pytest` 全綠(引最終輸出)
- [ ] `cd frontend && npm run typecheck && npm run lint && npm run build` 全綠(引最終輸出)

## 必讀檔(Just-in-time)

- `docs/Design-Base/99-code-review/00-overview.md`
- `docs/Design-Base/99-code-review/03-pr-self-check.md`
- `docs/Design-Base/99-code-review/06-security-checklist.md`
