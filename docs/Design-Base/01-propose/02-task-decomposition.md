# 02-task-decomposition — Tasks 拆解方法論

> **何時讀**:orchestrator agent(`/propose-to-tasks`)從 propose 拆 task 才讀;一般 worker **不**讀本檔。

---

## 拆解原則

- **粒度**:每 task **1–4 hr** 可完成
  - < 1 hr → 與相鄰 task 合併
  - > 4 hr → 再拆(不可能正確估這麼長)
- **獨立性**:盡量讓 tasks 可並行(unblocked)→ workers 同時認領
- **依賴顯示**:有依賴 → `depends_on: [task-XXX]`
- **同檔互鎖**:多 task 寫**同一檔** → 序列化(避免 worker 並行 merge conflict)
- **跨 area 依賴**:後端 API → 前端串接 → e2e,以三段 task 串

---

## 產出

`tasks-v{X.Y.Z}.md`(總清單)+ `tasks/task-NNN-<slug>.md`(細節)。

### tasks-v{X.Y.Z}.md(總清單)

```markdown
# Tasks v{X.Y.Z}

> 狀態:進行中(已完成 N/M)

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | 加 user-groups CRUD(後端) | done | ✓ | — | `app/api/v1/user_groups.py` 等 |
| 002 | user-groups 列表頁(前端) | in_progress | ✓ | 001 | `frontend/src/pages/UserGroups.tsx` |
| 003 | SSO callback | pending | ✗ | — | `app/clients/azure_ad/` |
```

### tasks/task-NNN-<slug>.md(細節)

```markdown
---
id: task-001
title: 加 user-groups CRUD
status: pending          # pending | in_progress | done | blocked
parallel: true
depends_on: []
affected_files:
  - app/api/v1/user_groups.py
  - app/services/user_group_service.py
  - app/repositories/user_group_repo.py
  - alembic/versions/xxxx_add_user_groups.py
estimated_hours: 3
---

## 目標
<1–2 句>

## Acceptance
- [ ] alembic upgrade head + downgrade -1 round-trip OK
- [ ] `/api/v1/user-groups` GET / POST / PATCH / DELETE 通過 pytest
- [ ] response 殼為 ApiResponse(`03-backend/01-routing.md`)
- [ ] mypy / ruff green

## 必讀檔(Just-in-time)
- `03-backend/00-overview.md`
- `03-backend/01-routing.md`
- `04-databases/00-overview.md`
- `04-databases/02-soft-delete.md`
- `04-databases/08-alembic.md`
```

---

## 拆解禁忌

- **禁** task 寫「重構整個 X」(粒度違反)→ 拆「重構 X 的 Y 子模組」
- **禁** 多 task 同時改 `00-overview/*` 或 `99-code-review/*`(規範底線檔)→ 序列化
- **禁** 跨版本 task(超出當版 propose scope)
- **禁** task 沒寫 `Acceptance`(無法驗證 done)
- **禁** task `affected_files` 寫 `*` / 整個資料夾(無法做衝突偵測)

## Acceptance 寫法

- 用 ✅ 可機械驗證的條件:CI 命令 / 檔案存在 / 行為斷言(`curl ... | grep`)
- ❌ 模糊:「跑得起來」「沒 bug」
- ✅ 具體:「`uv run pytest tests/api/test_user_groups.py` 全綠」
