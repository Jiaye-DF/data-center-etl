# Issue — Scan Project(2026-07-10 13:11 +08)

> focus=all;v1.4.1 五 task 收口後檢測(dev-v1.4.1/roles @ def1a0a,未 push)。
> 差異基準:`Issue-Scan-Project-260709131411.md`(2026-07-09,v1.4.0 收口後)。
> 掃描方式:v1.4.0 全域基準僅隔一日,本次以 **v1.4.1 diff 深掃**(26 程式檔、~1,800 行:roles 表 / 授權鏈路 / 使用者管理 API / 前端 users 頁)+ 舊項存續逐項確認(v1.4.1 未觸碰之區域沿用前次結論)。
> 已記錄於 `docs/Tasks/v1.4.1/fixed.md` 者視為已處理(§1 role_pid 過渡 nullable、§2 測試 DB drift、§3/§5 白名單過渡態、§4 seed 依賴、§6 Acceptance jq 外殼筆誤)。

---

## 0. 與前次差異

上次 🟠2 🟡6 🔵11 ⚪2 → 本次 🟠2 🟡6 🔵12 ⚪3。

### ✅ 已修(0 項)
v1.4.1 為純新增 feature(roles 結構收斂),未觸碰前次任何遺留項所在檔案 — 無舊帳清償,亦無舊帳惡化。

### ⏸ 仍在(21 項,全數原樣)
前次全部 🟠🟡🔵⚪ 逐項確認所在檔案於 v1.4.1 diff 之外、內容未變:R-SEC-002(login rate limit)、R-SEC-003(安全 headers)、AD-101(殭屍 run)、AD-102(同表並發)、AD-103(production adminer)、R-DEP-003(compose 直寫 postgres tag)、R-ENV-002(.gitignore 三樣式)、R-TEST-001(前端零測試)、AD-104~AD-107、R-DEP-005、R-DEP-002(redis 未登記)、R-ENV-004×2、R-SEC-004(fail-fast 弱密碼)、422 欄位級、/version、CI/依賴掃描 — 詳見前次報告第 3 章,不重複展開。

### 🆕 新增(3 項)
AD-108 🔵(dual-write 與 `ck_users_role` 的未來自訂角色地雷)、AD-109 ⚪(雙 admin 互降 race)、AD-110 ⚪(JWT `role` claim 成無消費者殘留)— 見第 3、6 章。

### 🔄 變化(0 項)

---

## 1. 總覽

| 項目 | 內容 |
| --- | --- |
| 掃描時間 | 2026-07-10 13:11 (UTC+8) |
| 範圍 | v1.4.1 diff 全檔深掃(backend 22 檔 + frontend 4 檔)+ 前次 21 項遺留存續確認 |
| 嚴重度統計 | 🔴 0 🟠 2 🟡 6 🔵 12 ⚪ 3(🟠🟡全數為前次遺留;v1.4.1 新碼僅新增 1🔵 2⚪) |
| 結論 | **v1.4.1 新碼品質高,無任何 Critical / High 級新發現**。授權鏈路收斂到單一入口(`resolve_role_code`)且 fail-fast、`lazy="joined"` 杜絕授權路徑 N+1、v7/v8 migration 全程 guard 可重入 + 無 DROP、自降防呆 + 稽核 + 輸入驗證齊備、前端三態 / ConfirmDialog / memo / 無 any 全合規。唯一值得在「權限矩陣版」動工前記住的是 AD-108:dual-write 撞 `ck_users_role` 的結構性時序約束。前次「立刻」清單(adminer / rate limit / 殭屍 run)依然是部署前優先事項。 |

---

## 2. 專案摘要

- **目標**:ETL 管理後台;v1.4.1 把角色自 `users.role` 字串欄位獨立為 `roles` 表(唯一事實來源)+ admin 可於系統內指派角色,為 DataHub API 權限矩陣鋪地基。
- **技術棧對照**:與前次一致(Next.js 16 + TS strict / FastAPI + SQLAlchemy 2 async / PostgreSQL 18),v1.4.1 未新增依賴。
- **Task 進度**:v1.4.1 5/5 done(tasks-v1.4.1.md),propose 7 項驗收全 pass(verification-v1.4.1.md);後端 239 passed、前端 typecheck/lint/build 綠。
- **完成度**:前端零測試、無 CI 仍為唯二成片缺口(⏸)。

---

## 3. 詳細發現(依嚴重度;⏸ 遺留項僅列 ID,細節見前次報告)

### 🟠 High(2 項,皆 ⏸)

- **[R-SEC-002]** `/api/v1/auth/login` 無 rate limit — `backend/app/api/v1/auth.py:44`(⏸ 自 2026-07-06;v1.4.1 僅改該檔角色取值來源,攻擊面不變)
- **[R-SEC-003]** 全棧缺安全 headers — `backend/app/main.py:41-59`、`frontend/next.config.ts:1-9`(⏸ 自 2026-07-06)

### 🟡 Medium(6 項,皆 ⏸)

AD-101(殭屍 run)、AD-102(同表並發防疊)、AD-103(production adminer)、R-DEP-003(compose 直寫 tag)、R-ENV-002(.gitignore 三樣式)、R-TEST-001(前端零測試)— 檔案與修正建議同前次報告第 3 章。補充一點:R-TEST-001 的「值得測的純邏輯」在 v1.4.1 又+1(`UserRoleTable` 的 pending/確認流與自列停用判斷)。

### 🔵 Low(12 項:11 ⏸ + 1 🆕)

### 🔵 [AD-108] dual-write 與 `ck_users_role` 的時序地雷 — 加入第三個角色前必須先處理 CHECK 約束 🆕
- 檔案:`backend/app/repositories/user_repo.py:89,103`(dual-write 寫入點)、`backend/app/models/user.py:52`(`ck_users_role` 僅允許 `('admin','viewer')`)、`docs/Tasks/v1.4.1/manual-removal-checklist.md`
- 內容:v1.4.1 決策為 deprecated `users.role` 字串在建立 / 指派時同步回寫同值(保舊欄位一致)。但 `ck_users_role` CHECK 僅允許 admin/viewer — 未來權限矩陣版一旦 seed 第三個角色(propose 決議點 2 已預告「API 使用者」情境),對該角色的**建立或指派會在 dual-write 當下違反 CHECK 直接 500**,且錯誤發生點(user_repo)與根因(v1.1 的 CHECK 約束)相距很遠,屆時不易定位。
- 白話:現在埋的相容寫入,會在「加第三種角色」那天變成炸彈,而且爆炸點看不出是這裡埋的。
- 修正:不必現在動(本版僅兩角色,行為正確)。在 `manual-removal-checklist.md` 前置條件段補一條「**新增任何非 admin/viewer 角色前**,須先移除 `ck_users_role`(走本清單人工流程)或先停止 dual-write」;並於未來權限矩陣版 propose 的風險段抄錄此條。
- 首次發現:2026-07-10

其餘 11 項 ⏸:AD-104(partial 三方不一致)、AD-105(巢狀 main)、AD-106(概覽列刷新)、R-DEP-005(compose 資源上限)、R-DEP-002(redis 未登記)、R-ENV-004×2(env example 漂移)、R-SEC-004(fail-fast 弱密碼)、422 欄位級、R-LOG-006(/version)、R-TEST-002/R-DEP-004(CI)。

### ⚪ Info(3 項:1 ⏸ + 2 🆕)

### ⚪ [AD-109] 雙 admin 互降 race 可致系統 0 admin 🆕
- 檔案:`backend/app/services/user_service.py:71-73`
- 內容:自降防呆只擋「對自己」;兩個 admin 同時互相降級(或 A 降 B 後 B 的舊頁面仍能發出降 A 請求)會讓系統無 admin,只能改 DB 救回。propose 風險段明示本版僅做「最小防呆(至少禁自降)」,故列 Info 記錄殘餘風險,不算違規。
- 修正(未來版):指派為降級時檢查「降級後 admin 數 ≥ 1」再放行。
- 首次發現:2026-07-10

### ⚪ [AD-110] JWT `role` claim 已無授權消費者,成殘留欄位 🆕
- 檔案:`backend/app/api/v1/auth.py:53`、`backend/app/services/sso_service.py:109`
- 內容:v1.4.1 後守衛一律每請求從 DB 關聯取角色,token 內 `role` claim 不再被任何授權判斷讀取;指派後舊 token 的 claim 值即過期失真(行為無害 — 沒人讀它,但誤導維護者以為改 claim 有授權效果)。
- 修正:留待 `users.role` 人工移除時一併決策(移除 claim 或註記「僅供 debug、禁作授權依據」);可加進 manual-removal-checklist 讀取點清單。
- 首次發現:2026-07-10

### ⚪ [07-testing] 測試建 schema 用 `create_all` 非 alembic(⏸ 自 2026-07-06;v1.4.1 fixed.md §2 的 drift 事件即此模式的直接後果,佐證前次建議)

---

## 4. 修正優先序

### 立刻(部署前;與前次一致,v1.4.1 無新增急項)
1. 🟡 AD-103 production adminer 收口
2. 🟠 R-SEC-002 login rate limit
3. 🟡 AD-101 殭屍 run 對帳

### 本週
4. 🟠 R-SEC-003 安全 headers;🟡 AD-102 同表並發防疊
5. 🔵 AD-108 → 只需在 `manual-removal-checklist.md` 補一條前置條件(5 分鐘,趁記憶新鮮)
6. 其餘同前次(compose 插值 / .gitignore / env example / fail-fast 弱密碼)

### 有空
7. 前端測試基建 + CI;AD-104~106;AD-109/110 記入未來權限矩陣版 propose 風險段

---

## 5. 已跳過類別 / 規則與脈絡衝突註記

- **組成偵測**:全類別存在,無跳過;v1.4.1 未觸碰之區域(worker / scheduler / etl / compose / CI)沿用前次結論,不重掃。
- **規則與脈絡衝突(不回報)**:
  - `resolve_role_code` / `get_role_by_code` 的 AppError detail 含「migration 未執行」營運提示 — 單語系內部後台 detail 直顯已於 v1.1.0 fixed.md §11 裁定可接受,沿用。
  - `tests/conftest.py:40` seed fixture fallback `changeme-development` 命中 R-ENV-001 樣式 — 值為 repo 內已公開的 development 預設(`.env.development.example` 同值),且 production fail-fast 護欄擋沿用,測試專用不回報。
  - `GET /roles` 無分頁(R-BE-011 的 total 欄)— 內建角色僅 2 筆且本版無 CRUD,`{items}` 外殼已合規,無後果不回報。
  - 前端繁中 literal(R-FE-004)— 單語系裁定沿用。
- **fixed.md 已載明不重複回報**:v1.4.1 §1~§6 全數(過渡 nullable、測試 DB drift、白名單過渡態、seed 依賴、jq 外殼筆誤)。

---

## 6. AD-xxx(規則外發現)

| ID | 嚴重度 | 摘要 |
| --- | --- | --- |
| AD-101~107 | 🟡×3 🔵×3 ⚪×1 | 前次遺留,全數 ⏸(見前次報告) |
| AD-108 | 🔵 | dual-write 撞 `ck_users_role`:加第三個角色前必先處理 CHECK 🆕 |
| AD-109 | ⚪ | 雙 admin 互降 race 可致 0 admin(propose 明示最小防呆,記錄殘餘風險)🆕 |
| AD-110 | ⚪ | JWT `role` claim 無授權消費者,成殘留欄位 🆕 |

**已巡視面向**(未發現額外問題者):授權鏈路單一入口(`resolve_role_code` 全 5 個取值點無旁路、fail-fast 無默默 fallback ✓)、eager load(`lazy="joined"` 授權/清單路徑皆無 N+1、async 無 MissingGreenlet 風險 ✓)、v7/v8 migration(存在性 guard 可重入、backfill 冪等、v8 殘留 NULL fail-fast、downgrade no-op、零 DROP ✓)、RBAC 覆蓋(`/roles` require_login、`/users` 兩端點 require_admin、401/403 語意分明 ✓)、輸入驗證(RoleAssignRequest min/max length、page/page_size ge/le 界限 ✓)、稽核(role_assigned 含 actor/target/舊→新 detail,同 session 隨請求 commit ✓)、軟刪除紀律(user/role 查詢全過濾 is_deleted、指派對已軟刪角色不可達 ✓)、外鍵索引(idx_users_role_pid ✓)、seed 冪等(v7 與 conftest 皆存在即跳過 ✓)、response 外殼(ApiResponse + items 包裝、無內部欄位外洩 ✓)、前端(三態齊備、ConfirmDialog confirmDisabled 防雙送、自列停用+提示、memo/useCallback 紀律、無 any、controlled select 取消即還原 ✓)、git(全 commit `(AI)` 前綴 + `[task-NNN]` tag ✓)。

---

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **`01-versions.md:25` 與三份 compose 的矛盾仍未收斂**(前次 #1,⏸)— 二擇一,不要繼續兩邊對不上。
2. **orchestrator 中途補規格未同步重掃白名單**(v1.4.1 fixed.md §3/§5 實證):task-002 中途追加 v8 migration 規格時,未盤點「固定過渡態的既有測試檔」也需入白名單,worker 被迫白名單外最小修正。建議 `02-task-decomposition.md` 補一條「task 規格於執行中變更 → `affected_files` 必須同步重掃(含測試檔)」,走 /reflect-rules。
3. **Acceptance 範本與 `01-routing.md` 外殼規範打架**(v1.4.1 fixed.md §6 實證):拆解層手寫 `jq '.data[]'` 裸陣列範例違反 `{items:[...]}` 外殼。建議 `02-task-decomposition.md § Acceptance 寫法` 的範例改用合規外殼路徑,杜絕下次抄錯。
4. **`03-backend/07-testing.md` 過薄**(前次 #2,⏸)— v1.4.1 fixed.md §2(create_all 不補欄位致 drift)再度佐證缺「測試 DB schema 與 migration 對齊」約定。

---

> 本次 🔴 0 🟠 2 🟡 6 🔵 12 ⚪ 3;v1.4.1 新碼零 Critical/High,新增僅 1🔵 2⚪(全屬「未來版本注意事項」性質)。前次「立刻」清單(adminer / rate limit / 殭屍 run)維持部署前優先。**需要我幫你修 High(🟠)與「立刻」清單嗎?**
