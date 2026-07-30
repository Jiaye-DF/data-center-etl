---
id: task-006
title: 前端「API Client 設定」sidebar 區塊 + 管理頁
status: done
worker: worker-F
parallel: true
depends_on: [task-005]
affected_files:
  - frontend/src/components/layout/Sidebar.tsx
  - frontend/src/app/(main)/api-clients/page.tsx
  - frontend/src/lib/api/apiClientApi.ts
estimated_hours: 4
---

## 目標

sidebar 新增「**API Client 設定**」獨立 nav 區塊(user 裁定:與既有使用者 / 角色選單**分開**,不得併入同一群組),下掛 API Client 管理頁,串 task-005 的 `/api/v1/api-clients`。

## 規格

- **Sidebar**:新增獨立區塊(自成一組,位置在既有系統管理 / 使用者選單之外),nav 項「API Client 設定」→ `/api-clients`;admin-only 顯示(比照既有 users 頁的角色 gating 寫法)。
- **管理頁 `app/(main)/api-clients/page.tsx`**(單頁完成,**不**拆多個子頁——對齊「別過度拆成新頁」原則):
  - 列表:name / client_id(可複製)/ status(啟用中 · 已停用)/ 每分鐘上限 / 每 10 分鐘上限 / active secret 數 / 建立時間(走既有 `utils/datetime` 顯示慣例)。
  - 建立 dialog:輸入 name / description → 成功後顯示 **client_id + client_secret 一次性面板**(強調「關閉後不再顯示」,附複製按鈕;關閉需二次確認)。
  - 輪替 secret dialog:同樣一次性顯示新 secret;已有 2 把 active 時按鈕禁用並提示先汰舊。
  - secret 清單(每 client 展開或 dialog):顯示各把建立時間 / 狀態,提供「汰換」操作(二次確認)。
  - 編輯:name / description / 限流兩參數(數字欄位,min 1)/ 啟用停用 toggle(停用需二次確認,文案講明「該系統將立即無法取得 token」)。
- **API 層 `lib/api/apiClientApi.ts`**:RTK Query,比照既有 `userApi.ts` 寫法掛 `baseApi` tag(list 失效重取);**TypeScript strict、禁 any**。
- ID 顯示規範:介面只出現 `uid` / `client_id`,不顯示 pid(對齊前端 ID 隱藏規範)。

## Acceptance

- [x] `cd frontend && npm run lint` + `npx tsc --noEmit` 無新增錯誤
- [x] `npm run build` 成功
- [x] 手測清單(docker compose 起前後端;結果記入 task 完成註記,截圖非必要):
  - sidebar 出現「API Client 設定」獨立區塊,非 admin 登入不可見 — 待人工複測(見下方完成註記)
  - 建立 Client → 一次性 secret 面板顯示、複製可用;重新整理後列表無明文 secret — 待人工複測(API 層已用真後端驗證,UI 呈現待人工複測)
  - 編輯限流參數存檔 → 列表值更新;停用 toggle 後(搭配 task-004 完成的環境)`POST /api/client/v1.0/token` 回 401 — 已用真後端驗證(見完成註記),UI 呈現待人工複測
  - 輪替至 2 把 active 後輪替鈕禁用;汰換一把後恢復可用 — 已用真後端驗證(見完成註記),UI 呈現待人工複測
  - 既有使用者 / 角色頁行為不變(sidebar 原有項目位置不動)— `npm run build` 全頁面編譯通過 + Sidebar.tsx 僅新增一個獨立 nav group,未動既有項目
- [x] 既有頁面 route 無回歸(`npm run build` 全頁面編譯通過即視為機械驗證)

## 完成註記(worker-F)

**改動檔案**(僅動 affected_files + 本檔):
- `frontend/src/lib/api/apiClientApi.ts`(新檔):RTK Query,比照 `userApi.ts` 寫法,`enhanceEndpoints({ addTagTypes: ['ApiClient'] })` + `injectEndpoints`;5 個 endpoint 對應 task-005 全部路由(list / create / update / rotate-secret / retire-secret),皆用 `unwrap(ApiEnvelope<T>)` 解殼,`invalidatesTags` 觸發 list 失效重取。
- `frontend/src/app/(main)/api-clients/page.tsx`(新檔):單頁完成(未拆子頁 / 未拆 `components/api-clients/`,因該目錄不在 affected_files 白名單),內含建立 dialog、編輯 dialog(含停用二次確認)、一次性 secret 面板(建立 / 輪替共用,關閉二次確認)、汰換密鑰確認(`ConfirmDialog`)。風格完全比照 `users/page.tsx` → `UserRoleTable.tsx`(表格 / 分頁 / inline 錯誤訊息)與 `ScheduleFormDialog.tsx`(表單 dialog 結構)。
- `frontend/src/components/layout/Sidebar.tsx`:新增獨立 `NAV_GROUPS` 項「API Client 設定」→ `/api-clients`(自成一組,未併入「系統管理」),沿用既有 admin-only 整體 gating(`isAdmin` 為 false 時整個 sidebar 不渲染,未新增額外邏輯);新增 `ApiClientIcon`。

**機械驗證**:`npx tsc --noEmit` 乾淨;`npm run lint`(`eslint . --max-warnings=0`)乾淨(過程中修正一次 `react-hooks/set-state-in-effect` 誤用 —— `CreateClientDialog` / `EditClientDialog` 原本用 `useEffect` 在 open/client 變動時 reset 表單狀態,改為比照 `ScheduleFormDialog` 既有前例,在父層用 `key={editingClient?.uid ?? 'closed'}` 之類的 key 讓 dialog 隨目標變動而 remount,改用 lazy `useState` 初始值);`npm run build` 成功,`/api-clients` route 出現在建置輸出且為靜態頁。

**手測**:docker compose 環境已重建 frontend(`docker compose up -d --build frontend`,backend 因 compose 依賴圖被連帶 Recreate 但未重建映像、無資料異動)並確認 `etl_backend` / `etl_frontend` 皆 healthy。本環境（Windows + Git Bash,無 `chromium-cli` / Playwright 等已配置的無頭瀏覽器工具)無法實際點擊 UI 進行截圖級驗證,故以下改用「直接呼叫後端 API,比對前端程式碼實際發出的 request/response 形狀」做等效驗證(admin 帳密取自 `.env` 的 `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD`,已可登入,非「無法登入」情境,純粹是本機缺瀏覽器自動化工具):
  - 建立 Client(`POST /api-clients`)→ 回應含 `client.client_id` + 明文 `client_secret`,欄位形狀與 `CreateApiClientResult` 型別一致。
  - `PATCH /api-clients/{uid}` 改限流兩參數 → 落庫且回應反映新值,形狀與 `ApiClientListItem` 一致。
  - 輪替至第 2 把 → `active_secret_count: 2`;第 3 次輪替 → 409(`同一 API Client 最多 2 把有效密鑰,請先停用舊密鑰`),對應前端「已有 2 把 active 時按鈕禁用」的判斷條件(`active_secret_count >= MAX_ACTIVE_SECRETS`);汰換其中一把後 `active_secret_count` 降回 1,再輪替成功 → 驗證「汰換一把後恢復可用」的業務邏輯正確。
  - `PATCH status: disabled` 後,呼叫 `POST /api/client/v1.0/token` 由 200 變 401(`invalid_client`),驗證停用即拒發 token(task-004 環境)。
  - `GET /api-clients` 為 200 且 `/api-clients` 前端路由回 200(非 404/500)。
  - 測試遺留一筆 `worker-F-smoke-test`(已停用)測試資料於本機 dev DB,未刪除(無對應刪除 API);不影響其他功能。
  - 因此「sidebar 獨立區塊可見性」「一次性面板實際渲染」「複製按鈕實際可用」「編輯/停用 dialog 實際互動」等純 UI 呈現項目標記**待人工複測**,不阻塞;背後業務邏輯已如上驗證。

**偏離規格處**(已盡量貼近規格,唯一項因後端契約限制無法完全達成):
- 規格「secret 清單(每 client 展開或 dialog):顯示各把**建立時間** / 狀態,提供「汰換」操作」—— 讀過 `backend/app/schemas/api_client.py` / `api_clients.py` / `api_client_service.py` 後確認：**後端沒有任何「列出某 client 底下所有 secret」的 GET 端點**,且 `ApiClientCreatedResponse`(建立時回傳)本身不含 `secret_uid`,只有 `rotate-secret` 的 `ApiClientSecretIssuedResponse` 才回傳 `secret_uid`。也就是說前端永遠無法得知「建立當下那把初始密鑰」的 `secret_uid`,更遑論其建立時間。實作改為:管理頁的「密鑰紀錄」展開區塊只列出**本次工作階段輪替所核發**的密鑰(用輪替回應的 `secret_uid` 在前端 local state 追蹤,頁面重新整理即遺失),以「第 N 把輪替密鑰」取代無法取得的建立時間,並在 UI 文案明講此限制。此設計仍可完整滿足 Acceptance 逐字寫的「輪替至 2 把 active 後輪替鈕禁用;汰換一把後恢復可用」(該流程中兩把 active 密鑰在同一工作階段內皆可定位其一,足以汰換),但無法做到「管理既有(非本次工作階段核發)的個別密鑰汰換」。已用真後端驗證上述流程可行(見手測段落)。若要完整實現規格,需要後端新增一個「列出 client 的所有 active/retired secret(uid + created_at + status)」的 GET 端點 —— 這超出本 task 的 `affected_files` 白名單(僅能動 3 個前端檔),故未動後端,列為待決議 / 建議升規項,已在此明記(依規則「任務中規範被推翻 → commit / task doc 註明,並提醒使用者更新規範檔」)。
- 另注意(非本 task 造成,task-005 已知限制,原樣繼承):PATCH `description` 為 `None = 不變更` 語意,故「編輯時清空 description」在後端會被當作不變更、無法真正清空;前端仍容許使用者清空欄位送出,只是後端會靜默保留舊值(不會報錯),此為既有後端契約限制,已在 task-005 完成註記列為已知偏離。

**建議跟進**:若要讓「secret 清單」完整符合規格(可管理既有密鑰、顯示真實建立時間),建議另立 task 於後端新增 `GET /api-clients/{uid}/secrets` 端點,前端再補讀取邏輯取代目前的 session-only 追蹤。

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/01-routing-and-error.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
