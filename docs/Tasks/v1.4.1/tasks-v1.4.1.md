# Tasks v1.4.1

> 狀態:待認領(已完成 0/5)

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | roles 表 + users 關聯欄位 + migration backfill | pending | ✗ | — | `backend/app/models/role.py`(新)/ `backend/app/models/user.py` / `backend/app/models/__init__.py` / `backend/alembic/versions/v7_add_v141_roles.py`(新)/ `backend/tests/test_models_v141.py`(新)/ `docs/Tasks/v1.4.1/manual-removal-checklist.md`(新) |
| 002 | 授權鏈路改由角色表驅動(守衛 / auth me / SSO,對外值零變化) | pending | ✗ | 001 | `backend/app/api/deps.py` / `backend/app/api/v1/{auth,sso}.py` / `backend/app/services/{auth_service,sso_service}.py` / `backend/app/repositories/user_repo.py` / `backend/tests/{test_auth,test_sso}.py` |
| 003 | 角色列表 API + 使用者清單 / 角色指派 API(admin only + 稽核 + 自降防呆) | pending | ✗ | 002 | `backend/app/api/v1/{roles,users}.py`(新)/ `backend/app/api/v1/__init__.py` / `backend/app/schemas/{role,user}.py`(新)/ `backend/app/services/user_service.py`(新)/ `backend/app/repositories/role_repo.py`(新)/ `backend/app/repositories/user_repo.py` / `backend/tests/test_users_api.py`(新) |
| 004 | 前端 — 使用者與角色管理檢視(admin only)+ API 串接 | pending | ✗ | 003 | `frontend/src/lib/api/userApi.ts`(新)/ `frontend/src/app/(main)/users/page.tsx`(新)/ `frontend/src/components/users/UserRoleTable.tsx`(新)/ `frontend/src/components/layout/Sidebar.tsx` |
| 005 | 端到端收口驗證 — 手測清單 + 對外承諾覆核 + 驗證紀錄 | pending | ✗ | 004 | `docs/Tasks/v1.4.1/verification-v1.4.1.md`(新) |

## 拆解摘要

- **總數**:5 個 task,預估 ~15.5 hr;後端 3(001、002、003)、前端 1(004)、e2e 收口 1(005)。
- **並行 / 序列**:並行 0、序列 5 — 單一依賴鏈 `001 → 002 → 003 → 004 → 005`。
  - 本版是授權鏈路的結構收斂,天然單線:DB 地基(001)→ 取值來源切換(002)→ 管理 API(003)→ UI(004)→ e2e(005)。
  - 同檔互鎖:002 與 003 同動 `user_repo.py`,且 003 依賴 002 收斂的「角色取值單一入口」→ 序列化,不可並行。
- **阻塞點**:001 是全鏈唯一地基(migration + backfill);002 是對外行為零變化的正確性關鍵(建議最強 model 執行)。
- **跨 area 三段鏈**:後端 API(001–003)→ 前端串接(004)→ e2e(005);Playwright 依 `05-CI/06-e2e.md` 預設 disabled,005 以機械化手測清單代替(對齊 v1.4.0 前例)。
- **In Scope 映射**(無 orphan):
  1. 新增 `roles` 表(seed admin / viewer)→ 001
  2. `users` 外鍵關聯 + backfill + deprecated 保留 → 001
  3. 授權鏈路改角色表驅動(守衛 / auth me / SSO me,行為不變)→ 002
  4. 角色列表後端 API(已登入可讀)→ 003
  5. 使用者角色指派(admin only + 自降防呆,UI 併入既有頁面體系)→ 003(後端)+ 004(前端)
  6. 稽核(指派動作入 audit_logs)→ 003(寫入)+ 005(覆核)
- **決議點處理**(依 propose 草稿內建預設拆解;user 執行 /propose-to-tasks 視為認可現狀):
  - 決議點 1:使用者角色指派 UI **入本版**(propose In Scope 已列)→ 003 / 004。若要改為純結構版,刪 propose 該條目後需重拆(003 縮減、004 取消)。
  - 決議點 2:**不**開自訂角色 CRUD,僅 seed admin / viewer(Out of Scope 明列)。
- **dual-write 註記**:deprecated `users.role` 字串在建立(002)與指派(003)時同步回寫同值 — 保持舊欄位與 `ck_users_role` 一致直到人工移除;此為拆解層決策,若 user 傾向舊欄位凍結不再寫,請回饋後調整 002 / 003。
- **model 建議(派工參考,保守分級)**:002 = opus/high(授權鏈路、對外零變化最難);001、003 = sonnet/high(migration backfill / 權限 API 正確性);004、005 = sonnet/medium。

## 執行前置(worker 認領須知)

- **分支**:本版為 feature,自 `main` 開分支(例 `dev-v1.4.1/roles`);與 SSO 429 / uvicorn workers 等部署 hotfix 互不阻塞(propose § 風險與相依)。
- **跑法**:改碼後以 `docker compose up -d --build` 驗證,**禁** start-dev。
- 認領協議照 `01-propose/03-multi-agent-flow.md`:改 task 檔 `status: in_progress` + 本清單註記 worker id;Acceptance 全綠才標 done;commit 帶 `[task-NNN]`。
- 全部 done 後 orchestrator 收口:`/scan-project` → 補洞 → `/reflect-rules` → PR。
