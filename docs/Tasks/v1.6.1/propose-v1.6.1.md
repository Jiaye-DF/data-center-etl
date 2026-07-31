# Propose v1.6.1

## 版本目標

DataHub API Gateway 模組②——「DataHub 後台 · 組織權限管理」落地:建立 **系統別(Service)→ 作業(Operation)→ 角色權限設定檔(Profile)→ Role** 的權限階層,加上**特例權限**(直綁 User、可設效期)與 **API Client(User)的 Role 指派**,讓管理員能在後台把「哪個外部使用者、經哪個作業、能看哪張表哪些欄位、可讀或可寫」整套建置完成,並可**預覽最終可見欄位**。本版只做權限的**維護面**(資料建置與管理介面);每請求的判斷面(權限引擎,模組③)與資料供應端點(模組④)為後續版本,將直接消費本版建好的權限資料。價值對象:管理員(一站式授權建置、Salesforce 式加法模型好稽核)、平台自身(模組③④的資料地基)。行為與資料模型完整遵循 `docs/Arch/datahub-api-gateway-arch.html` 模組②。

## In Scope

- **權限階層資料表整套**(全繼承 BaseModel:pid 內部主鍵 + uid 對外 + 軟刪除 + audit 欄位;FK 用 pid,API 對外一律 uid、禁曝 pid),依 Arch ERD:
  - `services`(系統別:erp / crm / hrm / bpm / zpos…,作業的分類容器,對應路由 `{service}` 分段)
  - `operations` + `operation_items`(作業歸屬一個系統別;items 定義作業的**表 × 欄位範圍**,`*` = 全欄位)
  - `permission_profiles` + `profile_operations` + `profile_items`(設定檔勾選可讀作業;授權巢狀在作業下:**Profile → Operation → Table → Column → Read / Edit**;同一張表在不同作業可設不同欄位與動作)
  - `roles` + `client_roles`(Role **必綁 1 個設定檔**,DB 層 NOT NULL 禁空角色;API Client **只綁 0..1 個 Role**)
  - `exception_sets` + `exception_operations` + `exception_items` + `client_exception_sets`(特例權限:結構同設定檔,直綁 User、`expires_at` 可設效期,NULL = 不設限)
- **系統別 / 作業管理**(後台 `/api/v1` CRUD + 前端管理介面):建系統別、系統別下建作業並勾選表 × 欄位範圍;表 / 欄位名採**語意層英文名**(與 API 回傳 JSON key 同一套),選項來源為既有 semantic_mappings 的 confirmed 映射,授權畫面即見即所得。
- **角色權限設定檔管理**(CRUD + 前端):勾選可讀作業 → 每個作業底下逐表逐欄設 `read` / `edit`(edit = 新增 / 更新 / 刪除;`*` = 全欄位);為欄位與動作授權的主要來源。
- **Role 管理**(CRUD + 前端):建立 / 編輯 Role,綁定 1 個設定檔(必綁、禁空)。
- **API Client 指派**(擴充既有「API Client 設定」管理流):指派 / 解除 Role(0..1);綁定 / 解除特例權限(0..N,可設效期);既有建立 / 輪替 / 啟停 / 註銷流程不動。
- **最終可見欄位預覽**:對單一 API Client 計算 **Role 設定檔 ∪ 特例權限(過濾已過期)**,逐作業取「設定檔在該作業下勾的欄位與動作 ∩ 作業範圍」,輸出 `{作業: {表: {欄位: read/edit}}}` 供前端預覽;**default-closed**——作業有綁但沒給表欄位授權 = 該作業預覽為空(作業開門、授權給欄位,兩者缺一不可)。此聯集 / 交集邏輯即模組③ 的權限展開語意,先在預覽落地供後續沿用。
- **加法模型**:只授予、無 deny;收權 = 修改設定檔 / 解除綁定 / 特例到期自動失效。
- **稽核**:權限異動(系統別 / 作業 / 設定檔 / Role / 指派 / 特例)寫入既有 audit log 機制。

## Out of Scope

- **模組③ 權限引擎**:每請求的作業級 403 判斷、TTL 權限快取與失效、JWT 請求上下文整合——本版僅預覽端點做一次性計算,不做每請求判斷路徑。
- **模組④ 資料供應 API**(`/api/client/v1.0/{service}/...` 資料端點、SQL 欄位投影、依表分組回應)——本版授權資料建好但尚無資料端點可消費。
- **edit 動作的實際寫入落地**(寫入 ETL-Hub / 是否寫回 ERP 屬 erp-writeback 另案)——本版 `edit` 僅為授權資料的動作標記。
- 權限快取機制與「異動後失效、下次請求生效」——引擎不存在,無快取可失效;稽核鏈以 audit log 為準。
- API Client 連接層(模組①)行為變更——token / refresh_token / 限流 / 鎖定 / 密鑰管理全部不動。
- 後台管理員(人)的登入與角色體系——沿用既有 DF-SSO + users 表 admin 判定,不與本版權限階層混用(本版階層只服務 API Client 機器身分)。
- 不處理其他既有遺留(scan backlog:adminer 外露、殭屍 run 等)。

## 對外承諾

- 後台 `/api/v1` 新增系統別 / 作業 / 設定檔 / Role / 特例權限的管理端點與 API Client 指派端點(admin 專用,路徑命名依既有 `/api/v1` 慣例,統一封套);既有端點行為與效能不變。
- Role 建立 / 編輯**必須**帶設定檔,未帶一律 422 / 409(禁空角色);刪除仍被 Role 綁定的設定檔、或刪除仍被 Client 綁定的 Role,一律擋下並回明確錯誤(不做連鎖刪除)。
- 特例權限 `expires_at` 到期後**自動失效**:預覽與(後續)權限展開一律過濾過期特例,無需人工解除。
- 預覽端點:對任一 API Client 回傳 `{作業: {表: {欄位: read/edit}}}` 結構;無 Role 且無特例 → 空;作業有綁但無表欄位授權 → 該作業空(default-closed)。
- 授權採用的表 / 欄位名與資料 API 回傳 JSON key 同一套(語意層英文名);無 confirmed 語意映射的表 / 欄位不可被授權(選不到)。
- 前端:管理介面可完成 Arch 後台管理流程 ⓪→③ 全程(建系統別 + 作業 → 建設定檔 → 組 Role → API Client 指派 + 特例 + 預覽);既有「API Client 設定」頁功能不受影響。
- 所有刪除為軟刪除(`is_deleted`),禁物理刪除;權限異動留有稽核紀錄。

## 風險與相依

- 技術風險:**新表數量多(11 張)**,migration 與 model / repo / schema 樣板量大——以既有 BaseModel / api_client 兩表為範本收斂,拆解時控制粒度。
- 技術風險:**授權 UI 複雜度高**(作業 × 表 × 欄位 × 動作巢狀矩陣)——UI 形式屬 task 層決策,但「逐表逐欄勾選 + `*` 全欄位」語意不得簡化;拆解時前端須依既有頁面風格,先讀錨點頁再動手。
- 技術風險:**預覽 = 未來引擎語意的前哨**——聯集 / 交集 / 過期過濾 / default-closed 的計算結果將被模組③ 直接沿用,語意錯誤會傳染;以測試逐情境鎖定(對齊 Arch「三情境對照」)。
- 資料相依:表 / 欄位選項依賴 **semantic_mappings confirmed 映射**——映射缺漏的表無法授權,屬既有資料治理範圍,不在本版修;預覽與授權畫面對缺映射情形須有明確空狀態,不得報錯。
- 架構相依:資料模型、綁定關係、聯集語意全部以 `docs/Arch/datahub-api-gateway-arch.html` 模組② 為準;偏離須回寫 Arch 文件。
- 第三方依賴:無新增(PostgreSQL / Redis 沿用既有)。
- 跨團隊阻塞:無。

## 驗收標準

- 後端 `cd backend && uv run pytest` 全綠;`uv run ruff check app tests` + `uv run mypy app` 無新增錯誤;前端 `npm run lint` + `npm run typecheck` 乾淨。
- Migration 驗證:`alembic upgrade head` 可從 v1.6.0 基準升級,11 張新表齊備且全含 BaseModel 欄位;`roles.permission_profile_pid` NOT NULL。
- 整合驗證(本地 docker compose,對齊 Arch 範例):
  - 建系統別 erp → 建作業 O1(範圍 T1(C11·C12)、T2(C21·C22)、T3(C31·C32))→ 建設定檔 P1 勾 O1 並授權 C11:read、C21:read/edit、C31:read → 建 Role 綁 P1 → 指派給 Client A → 預覽回 `{O1: {T1:{C11:read}, T2:{C21:edit}, T3:{C31:read}}}` 等價結構(read/edit 表徵依 schema 定案)。
  - default-closed:設定檔勾了 O1 但未給任何表欄位授權 → 預覽該作業為空。
  - 特例權限:綁一組已過期(`expires_at` < now)特例 → 預覽不含;未過期 → 納入聯集。
  - 防呆:建 Role 不帶設定檔 → 4xx;刪除被綁定的設定檔 / Role → 4xx 且資料不變。
  - 無 Role 且無特例的 Client → 預覽為空結構。
- 迴歸:v1.6.0 全部既有測試綠(token / 限流 / API Client 管理 / 註銷不受影響)。
- 手測(前端):依 Arch ⓪→③ 流程走完一輪(建系統別 + 作業 → 設定檔授權矩陣 → Role 綁定 → Client 指派 + 特例 + 效期 → 預覽)並截圖留驗證紀錄;既有「API Client 設定」頁建立 / 輪替 / 註銷仍正常。

## 決策記錄

- 2026-07-31:本版範圍 = **模組② 維護面整套**(階層資料表 + 管理 API + 前端 + 預覽),判斷面(模組③)與資料端點(模組④)明確遞延——依 user「dev-v1.6.1 主要是組織的問題,DataHub 後台 · 組織權限管理 模組② 區塊」指示劃界。
- 2026-07-31:資料模型 11 張表、綁定關係(Client 0..1 Role、Role 必綁 1 Profile、特例直綁可設效期)、加法模型與 default-closed 語意,全依 `datahub-api-gateway-arch.html` 模組② 定案內容,無另行發明。
- 程序註記:本 propose 由 AI 依 2026-07-31 指示起草(比照 v1.5.2 / v1.6.0 慣例),**user 複核後生效**;複核前不拆 tasks。

### 開放點(請 user 裁定)

1. **前端頁面組織**:權限管理(系統別 / 作業、設定檔、Role)是併入 sidebar 既有「API Client 設定」nav 區塊底下成組頁面,或另立「組織權限管理」nav 區塊?(預設傾向:同一 nav 區塊下分頁,對齊「別過度拆成新頁」慣例)
2. **預覽端點歸屬**:掛在 API Client 資源底下(如 `/api-clients/{uid}/effective-permissions`)即可,或需獨立模擬器頁?(預設傾向:掛 Client 底下,前端在 API Client 頁內預覽)
3. **特例權限是否需要「可重用的特例組」**:Arch ERD 為 `exception_sets` 獨立表(可綁多個 Client);若實務上特例都是一次性,可簡化為單 Client 專屬。(預設傾向:照 ERD 做可重用組)
