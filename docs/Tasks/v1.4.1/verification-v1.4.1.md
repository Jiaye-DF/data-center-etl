# v1.4.1 端到端收口驗證紀錄

> worker: claude-E(task-005)
> 執行日期:2026-07-10
> 執行方式:`docker compose up -d --build` 完整環境(非 start-dev),逐條覆核 propose 對外承諾與 Acceptance。

## 環境狀態

```
$ docker compose ps --format "table {{.Name}}\t{{.Status}}"
NAME            STATUS
etl_backend     Up 13 minutes (healthy)
etl_frontend    Up 13 minutes (healthy)
etl_postgres    Up 2 hours (healthy)
etl_redis       Up 2 hours (healthy)
etl_scheduler   Up 47 minutes (healthy)
etl_worker      Up 47 minutes (healthy)
```

全容器 healthy,無 unhealthy / restarting。**pass**

---

## 1. migration 後狀態(SQL)

```sql
\d roles
-- pid/uid/is_deleted/.../code/name/description/is_builtin;
-- uq_roles_code UNIQUE (code) WHERE is_deleted = false
-- 被 users.fk_users_role 參照

SELECT pid, code, name, is_deleted FROM roles ORDER BY pid;
 pid |  code  |  name  | is_deleted
-----+--------+--------+------------
   1 | admin  | 管理員 | f
   2 | viewer | 檢視者 | f

SELECT count(*) AS total_users, count(*) FILTER (WHERE role_pid IS NULL) AS null_role_pid FROM users;
 total_users | null_role_pid
-------------+---------------
           4 |             0

\d users
-- role            character varying(20) not null default 'viewer'  ← 舊欄位原樣保留
-- role_pid        bigint not null                                   ← v8 已收 NOT NULL
-- Check constraints: "ck_users_role" CHECK (role::text = ANY (ARRAY['admin','viewer']))  ← 原樣保留
-- Foreign-key constraints: "fk_users_role" FOREIGN KEY (role_pid) REFERENCES roles(pid)
```

- `roles` 表存在,`admin`(pid=1)/ `viewer`(pid=2)兩筆 seed 齊全
- 既有 4 筆 `users` 全數 `role_pid` 非 NULL(0 筆 NULL)
- `users.role` 舊欄位(varchar(20), default 'viewer')與 `ck_users_role` CheckConstraint 原樣保留未動

**pass**

---

## 2. 對外值零變化

```
# admin(init-admin / .env INIT_ADMIN_PASSWORD)登入 + /me
$ curl -i -c cookies -X POST /api/v1/auth/login -d '{"username":"init-admin","password":"***"}'
HTTP/1.1 200 OK
{"success":true,"data":{"uid":"...","username":"init-admin","display_name":null,"role":"admin","provider":"local"},...}

$ curl -b cookies /api/v1/auth/me
{"success":true,"data":{"uid":"...","username":"init-admin","display_name":null,"role":"admin","provider":"local"},"response_code":200}

# viewer(既有測試帳號 viewer-test,暫改 password_hash 供本次登入驗證,驗證後已軟刪)
$ curl -i -c cookies2 -X POST /api/v1/auth/login -d '{"username":"viewer-test","password":"e2e-verify-temp-pw"}'
HTTP/1.1 200 OK

$ curl -b cookies2 /api/v1/auth/me
{"success":true,"data":{"uid":"...","username":"viewer-test","display_name":null,"role":"viewer","provider":"local"},"response_code":200}
```

- 欄位名為 `role`(非改名),值為 `admin` / `viewer` 字串,與 v1.4.0 一致
- 程式碼佐證:`git diff e7a101c HEAD -- backend/app/api/v1/auth.py` 顯示 `UserResponse` 序列化仍是
  `role=` 欄位,唯一變化是取值來源由 `user.role`(舊字串欄位)改為
  `resolve_role_code(user)`(經 `role_pid → roles.code` 衍生),回應 schema/欄位名/值域**零變化**

**pass**

---

## 3. 授權行為零變化

```
# viewer 呼叫寫入類 API(角色指派)
$ curl -X PATCH /api/v1/users/{uid}/role -b viewer_cookies -d '{"role":"admin"}'
HTTP 403 {"success":false,"data":null,"detail":"權限不足","response_code":403}

# admin 呼叫同一 API
$ curl -X PATCH /api/v1/users/{uid}/role -b admin_cookies -d '{"role":"admin"}'
HTTP 200 {"success":true,"data":{...,"role":"admin"},"response_code":200}
```

- viewer → 403、admin → 2xx,符合預期
- SSO 首次登入為 viewer:引 pytest — `backend/tests/test_sso.py`
  `test_first_sso_login_creates_viewer_user`(`assert user.role == "viewer"`)、
  `test_first_sso_login_links_viewer_role`(`assert user.role_ref.code == "viewer"` 且
  `user.role == "viewer"` dual-write 同值);另有 `/auth/me`、`/sso/me` 回應層測試
  斷言 `data["role"] == "viewer"`(全數列於本次 pytest 239 全綠內,見第 5 項)

**pass**

---

## 4. 指派即時生效

以 `closeout-viewer`(dev DB 既有測試帳號,驗證後已軟刪)實測 viewer ↔ admin 互換:

```
$ curl -X PATCH /api/v1/users/8ffc58e6.../role -b admin_cookies -d '{"role":"admin"}'
{"success":true,"data":{...,"username":"closeout-viewer","role":"admin"},"response_code":200}

$ psql -c "SELECT username, role, role_pid FROM users WHERE username='closeout-viewer';"
 username        | role  | role_pid
 closeout-viewer | admin |        1        ← dual-write 同步(role 字串欄位與 role_pid 一致)

$ psql -c "SELECT action, target_type, target_uid, actor_username, detail, created_at
           FROM audit_logs WHERE action='role_assigned' ORDER BY created_at DESC LIMIT 3;"
 role_assigned | user | 8ffc58e6... | init-admin | viewer → admin | 2026-07-10 12:50:22
 role_assigned | user | 87d915dd... | init-admin | admin → viewer | 2026-07-10 12:44:45
 role_assigned | user | 87d915dd... | init-admin | viewer → admin | 2026-07-10 12:44:38

# 再降回 viewer 恢復原狀
$ curl -X PATCH /api/v1/users/8ffc58e6.../role -b admin_cookies -d '{"role":"viewer"}'
{"success":true,"data":{...,"role":"viewer"},"response_code":200}
```

- 指派後立即透過 `GET /api/v1/users` 反映新角色(無需重啟服務);`audit_logs` 可查到
  `role_assigned` 動作(actor / target / detail 皆完整)
- 「重新整理後即時反映」佐證:`backend/app/api/deps.py::get_current_user` 每個請求皆用
  JWT 內 `sub`(uid)**重新查 DB**(`AuthService.get_user_by_uid`),`require_admin` 再用
  `resolve_role_code(user)` 即時判斷,並非讀 JWT 內嵌的舊 role claim → 指派後下一次請求
  (含前端 reload 觸發的 `/auth/me`)即反映新角色,不需重新登入
- **UI 三項僅以 API + 程式碼審查佐證,無真實瀏覽器點擊驗證(見下方「待人工複測」)**

**pass(API 層);UI 視覺呈現待人工瀏覽器複測**

---

## 5. 全套迴歸

### 後端

```
$ cd backend && uv run pytest -q
........................................................................ [ 30%]
........................................................................ [ 60%]
........................................................................ [ 90%]
.......................                                                  [100%]
239 passed in 80.78s (0:01:20)
```

**pass**(239/239 全綠)

補充(非本 task 規格必列項,順帶記錄):`uv run mypy app` → `Found 1 error in 1 file`
(`app/repositories/schedule_repo.py:528 "Result[Any]" has no attribute "rowcount"`),
經 `git log` 確認該檔非本版(001~004)異動範圍,源自 v1.3.2(commit `8f00507`)既有基線,
**本版零新增 mypy 錯誤**。

### 前端

```
$ cd frontend && npm run typecheck
> tsc --noEmit
(無輸出,exit 0)

$ npm run lint
> eslint . --max-warnings=0
(無輸出,exit 0)

$ npm run build
▲ Next.js 16.2.7 (Turbopack)
✓ Compiled successfully in 12.4s
  Running TypeScript ... Finished TypeScript in 9.9s
✓ Generating static pages using 7 workers (11/11)
Route (app): / /_not-found /icon.svg /login /no-access /runs /runs/[uid]
             /schedules /sources /sources-hub /users
```

**pass**(typecheck / lint / build 三項全綠,`/users` 路由已納入 build 產物)

---

## 6. 無 DROP

```
$ grep -i -E "drop_table|drop_column|DROP TABLE|DROP COLUMN" backend/alembic/versions/v7_add_v141_roles.py
(無輸出,exit code 1)
```

`v7_add_v141_roles.py` 無任何 DROP 語句。另檢查 `v8_enforce_users_role_pid_not_null.py`
(承接 fixed.md §1 收 NOT NULL 的後續 migration)亦無 DROP。

**pass**

---

## 7. 人工移除清單

```
$ [ -f docs/Tasks/v1.4.1/manual-removal-checklist.md ] && echo exists
exists
```

檔案存在,內容列有 `users.role` 字串欄位 + `ck_users_role` 約束之前置條件與移除步驟
(§「目前已知讀取/寫入 users.role 字串欄位的位置」§「移除步驟」)。

**pass**

---

## dev DB 測試殘留處理

沿用 orchestrator 指示,以軟刪(`is_deleted = true`,禁 DELETE/DROP/TRUNCATE)清理前面
worker 手測遺留的 3 個測試 viewer 帳號:

```sql
UPDATE users SET is_deleted = true, updated_at = now()
WHERE username IN ('viewer-test', 'closeout-viewer', 'acc-viewer-probe') AND is_deleted = false;
-- UPDATE 3

SELECT pid, username, role, is_deleted FROM users ORDER BY pid;
 pid |     username     |  role  | is_deleted
-----+------------------+--------+------------
   1 | init-admin       | admin  | f
   2 | viewer-test      | viewer | t
   3 | closeout-viewer  | viewer | t
   4 | acc-viewer-probe | viewer | t
```

註:`viewer-test` 的 `password_hash` 於第 2 項驗證時暫改為已知測試密碼
(`e2e-verify-temp-pw`,經 `backend.app.core.security.hash_password` 產生)供登入取值比對,
帳號已隨本次收口軟刪,不影響現行帳號安全性。

歷史失敗 sync run(`dbo.acc_probe_nonexistent`,`etl_run_logs.pid=3460`,
`status=failed`)屬歷史紀錄,予以保留、僅記錄如下,未刪除 / 未修改:

```
 pid  | source_schema |     source_table      | status |                 error_message
------+---------------+-----------------------+--------+------------------------------------------------
 3460 | dbo           | acc_probe_nonexistent | failed | 來源表無欄位或不存在:dbo.acc_probe_nonexistent
```

---

## 待人工瀏覽器複測清單

本次執行環境無瀏覽器自動化工具,以下 3 項僅以「API 實測 + 程式碼審查」佐證,**尚未經真實
瀏覽器點擊驗證**,列入待人工複測:

1. **Sidebar 顯示 admin-only**:`frontend/src/components/layout/Sidebar.tsx` 第 121~122 行
   `if (!isAdmin) return null`(整個側欄不渲染,非僅隱藏「使用者與角色」單一項目,此為
   v1.4.0 既有 RBAC 導覽隱藏模式,task-004 規格明載沿用不新造守衛);「使用者與角色」項目
   本身定義於第 37 行,僅在側欄渲染分支內才會出現
2. **viewer 直開 `/users` 導向 `/no-access`**:`frontend/src/app/(main)/layout.tsx` 第 71~81 行
   RBAC guard,`!isAdmin && pathname !== '/no-access'` → `router.replace('/no-access')`;
   此守衛涵蓋整個 `(main)` 路由群組(非僅 `/users`),為 v1.4.0 既有機制,task-004 規格
   明載「若既有機制已按 role 全域涵蓋則不需改 layout,禁另造守衛」— 已確認未新造
3. **admin 自己那列的角色下拉停用**:`frontend/src/components/users/UserRoleTable.tsx`
   第 78~91 行,`isSelf` 為真時 `<select disabled title="無法變更自己的角色">`

---

## 總結

| # | 驗證項 | 結果 |
| --- | --- | --- |
| 1 | migration 後狀態(SQL) | pass |
| 2 | 對外值零變化 | pass |
| 3 | 授權行為零變化 | pass |
| 4 | 指派即時生效 | pass(API 層;UI 視覺待人工複測) |
| 5 | 全套迴歸(pytest / typecheck / lint / build) | pass |
| 6 | 無 DROP | pass |
| 7 | 人工移除清單 | pass |

7 項全數 pass,`docker compose ps` 全容器 healthy。UI 三項(Sidebar / no-access 導向 /
自己列停用)以程式碼審查佐證通過,列入待人工瀏覽器複測(不計入 fail)。
