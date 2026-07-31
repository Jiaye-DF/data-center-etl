# Issue Scan — data-center-etl(260731160551)

> 掃描時間:2026-07-31 16:05 (UTC+8)|範圍:v1.6.1 全部新碼(`dev-v1.6.1`,commit effd8e0→0726a17 共 9 筆 [task-001]~[task-011],約 37 檔 +10,300 行)+ 前次遺留存續確認|方法:三區域(後端權限模組/前端兩頁/ENV·GIT·DEP·docs+遺留)並行掃描彙整
> v1.6.1 無 fixed.md。既定裁定(12 表落 RDS `client_setting` 不走 alembic、naive UTC+8、快取 TTL300s、測試真 PG、單語系)均尊重不報。

## 0. 與前次差異(前次:Issue-Scan-Project-260730160810.md)

前次報告面 🔴0 🟠5 🟡20 🔵13 ⚪3,其中 15 項已於該報告第 8 章收口窗口修畢 → **修正後基準 🔴0 🟠2 🟡7 🔵13 ⚪3**。本次:

- 🆕 新增 15 項:**AD-151~AD-165**(🔴1 🟠3 🟡8 🔵3)— 全部來自 v1.6.1 新碼與其文件,含 1 條 Critical(AD-157 前端 page_size 超上限,作業範圍編輯器 100% 不可用)
- ✅ 已修 0 項(前次修正已計入基準;本次無新修)
- ⏸ 仍在 12 項:🟠2(R-SEC-002、R-SEC-003)、🟡7(AD-101、AD-102、AD-103、AD-140、R-TEST-001、R-ENV-004 staging/production 兩金鑰〔部署 blocker,grep key 名仍零命中〕、R-ENV-004 本機 .env 缺 14 key)、🔵 遺留群(AD-104~108、AD-149〔待 user 裁定〕、AD-150、R-DEP-005/002、R-ENV-004 舊案 ×2、R-LOG-006、CI 群)— 所在檔案本版零異動,逐條證據已重驗
- 🔄 變化 2 項:**R-TEST-001 痛感升級**(本版新增 2,698 行前端高後果權限矩陣邏輯零測試,AD-157 正是前端測試最能接住的類型);**測試 env 硬覆寫 pattern 第 6 批佐證**(v1.6.1 五個新測試檔全部 `os.environ[...]` 硬覆寫非 setdefault — reflect 候選權重再 +1)
- 合計現況:**🔴1 🟠5 🟡15 🔵16 ⚪3**

## 1. 總覽

| 項目 | 值 |
| --- | --- |
| 嚴重度統計 | 🔴 1(🆕)🟠 5(3 🆕 + 2 ⏸)🟡 15(8 🆕 + 7 ⏸)🔵 16(3 🆕 + 13 ⏸)⚪ 3 |
| 結論 | v1.6.1 後端核心品質高:展開演算法(來源配對/∩ 範圍/`*` 分支/action 取高)、33+1 端點 require_admin 全覆蓋、注入面、稽核 16 路徑零機密、快取失效扇出逐條核對一致、批次置換原子性,均乾淨。新發現集中四群:**(a) 可用性斷點**(AD-157 前端 page_size 422 → 整條授權鏈空轉;e2e 只做 API 層等價覆蓋所以沒踩到)、**(b) 部署斷點**(AD-151 schema 無建置入口,上站即整模組 500 — verification 已列待辦,本次落成 AD 並具體化)、**(c) 跨庫/跨層一致性**(AD-152 註銷孤兒死路、AD-158/160 前端快取失效缺口、AD-154 語意改名作廢授權)、**(d) 併發**(AD-153 置換聯集,AD-135 同族但 unique 兜不住)。🔴🟠 五條建議收口窗口修畢再部署 |

## 2. 專案摘要

- 目標:v1.6.1 = DataHub 模組② 組織權限管理維護面 — RDS ETL-Hub `client_setting` schema **12 張**權限表(唯一真身,多機共讀;propose 原寫 11 為計數筆誤,tasks 已勘誤)、`/api/v1/client-settings/*` 33 管理端點 + `GET /api-clients/{uid}/effective-permissions` 預覽、Redis cache-aside 讀取快取(TTL 300s、異動失效、故障降級直讀)、前端 client-settings 四分頁授權管理 + api-clients 權限對話框
- 技術棧:Next.js 16 + TS strict / FastAPI + SQLAlchemy 2 async / PostgreSQL — 與 CLAUDE.md 鎖定棧一致;**零新增依賴**(pyproject/uv.lock/package.json 本版零 diff)
- Task 進度:v1.6.1 11/11 done;後端 548 passed、ruff/mypy 綠;前端 lint/tsc 綠(零測試 R-TEST-001 ⏸);verification-v1.6.1.md 與 tasks 清單口徑一致(無前次 AD-148 型矛盾)
- Git:9 筆 commit 全數符合 `(AI) <類型>: <描述> [task-NNN]` 規範;無不當追蹤檔

## 3. 詳細發現(依嚴重度;⏸ 遺留僅列 ID,細節見前次報告)

### 🔴 Critical(1 項,🆕)

#### 🆕 [AD-157] 作業範圍編輯器欄位清單永遠 422:`page_size=500` 超過後端上限 200,錯誤被吞成誤導文案,整條授權鏈空轉
- 檔案:`frontend/src/app/(main)/client-settings/page.tsx:68`(`COLUMN_PAGE_SIZE = 500`)、`:499-513`(未取 `isError`)、`:618-624`(誤導分支);對照 `backend/app/api/v1/semantic_mappings.py:54`(`Query(ge=1, le=200)`)
- 內容:每個 admin、每次操作、100% 重現。選任一資料表後 `GET /semantic-mappings?page_size=500` 被 FastAPI 參數驗證擋下回 422 → `columnData` 恆 `undefined` → 畫面顯示「此表尚未確認『表層級』語意映射,後端不接受授權」,連「全欄位(*)」快捷一併被藏。結果:**作業範圍設不了 → 矩陣無列可勾 → 設定檔/特例/Role 整條鏈實質不可用**,且文案把 admin 導去做一件已做完的事。verification 明載 UI 互動「環境受限待補」、僅 API 層等價覆蓋,故收口未踩到。
- 修正:`page.tsx:68` 改 `COLUMN_PAGE_SIZE = 200`;`:512-513` 取出 `isError` 顯示 `<InlineError message="載入欄位選項失敗,請稍後再試" />`,任何載入失敗不得再偽裝成「尚未確認映射」。若單表 confirmed 欄位 >200 需改分頁累積取。
- 首次發現:2026-07-31

### 🟠 High(5 項:2 ⏸ + 3 🆕)

- [R-SEC-002] SSO login rate limit(`backend/app/api/v1/auth.py` grep 零命中,本版未動)— ⏸ 自 2026-07-06
- [R-SEC-003] 安全 headers(`backend/app/main.py` 僅 request_id + CORS middleware)— ⏸ 自 2026-07-06

#### 🆕 [AD-151] RDS 權限 12 表在正式環境沒有任何建置入口(部署即整模組 500)
- 檔案:`backend/app/etl/client_setting_schema.py:395`(`ensure_client_setting_schema_on_target()` 全專案零呼叫端)
- 內容:lifespan 沒呼叫、`backend/scripts/` 無對應腳本、worker/scheduler 也沒有;唯一建表的是四個測試檔。對照前例 `semantic_schema` 有 `scripts/seed_semantic_mappings.py:160` 當入口。部署到測試站/正式站後 `client_setting` schema 不存在 → 33 端點 + 預覽全吃 `UndefinedTable` → catch-all 轉 500,前端整頁不可用且看不出根因。本版唯一「本地全綠、上站全紅」項(verification 遺留 #3 已記,此處落成 AD 並具體化)。
- 修正:新增 `backend/scripts/ensure_client_setting_schema.py`(比照 `seed_semantic_mappings.py`:`asyncio.run` + 呼叫 `ensure_client_setting_schema_on_target()`)並列入部署 runbook;或 `main.py` lifespan 內 try/except 包覆呼叫(RDS 不可達不擋啟動)。
- 首次發現:2026-07-31

#### 🆕 [AD-152] API Client 註銷後,RDS 側指派/綁定成為解不掉的孤兒,Role 與特例組永久刪不掉
- 檔案:`backend/app/services/api_client_service.py:189-194`、`backend/app/services/client_setting_service.py:1111, 1196, 1351, 1444`、`backend/app/repositories/client_setting_repo.py:600-606`
- 內容:完整死路 — (1) `delete_client` 只動自有 DB,不碰 RDS `client_roles`/`client_exception_sets`;(2) `delete_role` 用 `count_clients_by_role` 擋 409,該 count 不知道 client 已註銷 → 永遠 >0;(3) 唯一解除入口 `remove_client_role` 第一行 `_ensure_client_exists` → client 已軟刪 → 404;(4) 特例組完全同型。管理員註銷一個已指派 Role 的 Client 後,該 Role 再也刪不掉,UI 說「請先解除指派」但清單裡沒有任何 client 可解;唯一出路是人工連 RDS 下 SQL。附帶:`delete_client` 也沒失效 `client_setting:effective:<uid>`。
- 修正(建議兩者都做):(a) `api_client_service.py:194` 後補 RDS 清理 — repo 新增 `soft_delete_client_grants(api_client_uid, actor)`(同 RDS 交易軟刪兩表該 client 列),commit 後 `invalidate_clients(uid)`;跨庫失敗只 log 不擋註銷。(b) `client_setting_service.py:1351/:1444` 移除 `_ensure_client_exists`(存在檢核保留在 assign/bind 兩條新增路徑),讓解除/解綁對已註銷 client 仍可執行。
- 首次發現:2026-07-31

#### 🆕 [AD-158] RTK 失效標籤打空氣:`id:'LIST'` 無任何 provider,取消勾選→再勾回後矩陣顯示後端已刪光的舊授權且「已與伺服器一致」
- 檔案:`frontend/src/lib/api/clientSettingApi.ts:450-453`(`replaceProfileOperations` invalidates `{type:'ClientSettingProfileItems', id:'LIST'}`)、`:575-578`(特例組同型)、`:355-357`(`deleteOperation` 同型);對照 provider `:464-466`(`id: ${uid}-${operationUid}`)、`:366-368`(`id: uid`)
- 內容:RTK Query 帶 id 的失效是精確比對,`'LIST'` 匹配不到任何條目 = 沒失效。後端 `replace_profile_operations` 會同交易清除被移除作業的授權項;前端快取沒失效 → admin 取消勾選存檔、再勾回、回矩陣看到**刪除前的舊勾選**,且 draft==舊快取 → `dirty=false`、儲存鈕 disabled — 他無法把畫面上的授權寫回去,也不知道要重整。結局:admin 以為權限還在,後端已 default-closed,對外 Client 靜默斷料。
- 修正:三處拿掉 `id`,改整型失效 — `:452` → `{type:'ClientSettingProfileItems'}`、`:577` → `{type:'ClientSettingExceptionItems'}`、`:356` → `{type:'ClientSettingOperationItems'}`。
- 首次發現:2026-07-31

### 🟡 Medium(15 項:7 ⏸ + 8 🆕)

#### 🆕 [AD-153] 整批置換系列 read-then-write 無鎖,雙管理員併發存檔落地為兩邊聯集(授權被放大)
- 檔案:`backend/app/repositories/client_setting_repo.py:299, 453, 500, 799`
- 內容:`replace_operation_items` / `replace_profile_operations` / `replace_profile_items` / `replace_exception_operations` 皆「讀舊集合→軟刪→插新」,未鎖父列;READ COMMITTED 下兩交易各刪自己看到的舊列、各插自己的新集合,新集合不重疊時兩邊都成功 → DB 為 A∪B。被移除的授權沒被移除、雙方畫面都顯示已儲存 — 錯誤方向是**放大**。AD-135 同族,但這裡 partial unique 兜不住。窗口窄但無聲。
- 修正:repo 父表取件方法加 `for_update` 參數(`with_for_update()`),`client_setting_service.py` 四條置換路徑(`:833/:952/:1000/:1235/:1289`)在 `_rds_write` 交易開頭以鎖定版取父列,同父列置換序列化為「後者覆蓋」。
- 首次發現:2026-07-31

#### 🆕 [AD-154] 授權以語意層 english_name 純字串儲存,而 english_name 可自由改名且無唯一約束 — 改名靜默作廢/錯接既有授權
- 檔案:`backend/app/models/client_setting.py:206-213, 314-321`、`backend/app/services/client_setting_service.py:454-471`、`backend/app/services/semantic_admin_service.py:134-136`、`backend/app/etl/semantic_schema.py:34-45`
- 內容:三張 items 表存英文名字串,與 `semantic_mappings` 無 FK;該表 PK 是 `(table_name, column_name)`,english_name 無唯一約束,且 admin 可任意 PATCH confirmed 列的 english_name。驗證只在寫入授權當下。改名 → 既有授權指向不存在的名字,靜默失效但預覽照列;更糟:english_name 不唯一,A 表英文名改成 B 表原名 → 既有授權**改指向另一張表**。今天實害止於預覽失真;`effective_permission_service.py` 檔頭明講模組③(每請求判斷)將沿用本檔,屆時就是資料越權。
- 修正(至少做最小版):`semantic_schema.py:34` 冪等 DDL 補 `CREATE UNIQUE INDEX IF NOT EXISTS uq_semantic_mappings_english ON erp_metadata.semantic_mappings (english_name) WHERE column_name = ''`(先清重);完整版另在 `update_mapping` 改 confirmed english_name 前反查三張 items 表引用,有引用則 409 或同交易連動改名 + `invalidate_all_effective()`。模組③ 前必處理。
- 首次發現:2026-07-31

#### 🆕 [AD-159] 三個整批置換編輯器在讀取失敗時仍可編輯並儲存,會用空草稿把既有設定整批洗掉
- 檔案:`frontend/src/app/(main)/client-settings/page.tsx:450/466-471/705-711`(範圍)、`:1287-1312/1470-1476`(矩陣)、`:1554-1578/1679-1685`(勾作業)
- 內容:GET 失敗時草稿與 serverKeys 都算成 `[]`,錯誤紅字顯示在上方但勾選 UI 完全可互動;admin 看到「空的」畫面勾一項儲存 → PUT 整批置換 → 原本 N 項授權被換成 1 項。讀(Redis 快取+`_rds_read`)寫(`_rds_write`)路徑不同源,讀失敗寫成功是實際組合;新環境 schema 未建時(AD-151)也是讀先炸。
- 修正:三處加 `loadFailed = isError || data === undefined`,`EditorActions` `disabled={!dirty || saving || loadFailed}`,`loadFailed` 時勾選區改渲染錯誤+重試,不給編輯入口 —「沒讀到現況就不准整批覆蓋」。
- 首次發現:2026-07-31

#### 🆕 [AD-160] 跨檔失效缺口:client-settings 的任何權限異動都不失效 effective-permissions,預覽照舊顯示改動前權限
- 檔案:`frontend/src/lib/api/clientSettingApi.ts`(11 支寫入端點只失效自家 10 tag)vs `frontend/src/lib/api/apiClientApi.ts:255-263`(`getEffectivePermissions` 提供 `ApiClientPermission`)
- 內容:admin 改完矩陣/改綁設定檔,切到 API Client 頁開預覽 — 只要該 client 預覽 60s 內被查過(對話框開著則無限期),看到的是舊結果且無任何快取訊號;admin 可能誤判「後端沒吃到」重複操作或誤信已收斂。後端失效有做,缺的是前端這層。
- 修正:`clientSettingApi.ts` 寫入端點(至少 replaceProfileItems/replaceProfileOperations/replaceExceptionItems/replaceExceptionOperations/updateClientSettingRole/replaceOperationItems/deletePermissionProfile/deleteExceptionSet)的 `invalidatesTags` 補 `{type:'ApiClientPermission'}`(同一 baseApi,跨檔可用)。
- 首次發現:2026-07-31

#### 🆕 [AD-161] ClientPermissionDialog 的 Esc 未分流 — AD-142 同型重現
- 檔案:`frontend/src/app/(main)/api-clients/page.tsx:1176-1183`(無條件 `onClose()`)vs 同檔 `:596`(編輯對話框已修成 `!confirmingDisable` 守衛)、`components/common/ConfirmDialog.tsx:27-34`
- 內容:權限對話框內按「解除指派/解除綁定」叫出二次確認後按 Esc → 兩個 listener 同時觸發,ConfirmDialog 關閉同時整個權限對話框也關,連帶清掉已選特例組與已填效期。
- 修正:比照 `:596` — 子層 confirm 開關狀態上提(或 `onNestedDialogChange` 回呼),`onKey` 加 `&& !hasNestedDialog`。
- 首次發現:2026-07-31

#### 🆕 [AD-162] Role 指派「選了就直接 PUT」無確認,與同區「解除指派」有確認形成反向不對稱
- 檔案:`frontend/src/app/(main)/api-clients/page.tsx:837-848`(change 即 `assignClientRole`)vs `:896-907`(解除走 ConfirmDialog)
- 內容:放行(把整組表×欄位授權給對外 Client)沒確認、收回反而要確認 — 高後果那邊防護較低;下拉在鍵盤/滾輪下易誤觸,誤觸即時對外生效。同頁其他高後果操作(停用/註銷/輪替/解除)全有二次確認。
- 修正:`:837` 改存 `pendingRoleUid` + ConfirmDialog(文案帶 Role 名與生效說明),確認後才 PUT;取消還原 select 為 `currentRoleUid`。
- 首次發現:2026-07-31

#### 🆕 [AD-163] 多支清單查詢未接 isError,失敗退化成「尚無…」空狀態,把系統故障說成資料不存在(R-FE-005/007 同族)
- 檔案:`frontend/src/app/(main)/client-settings/page.tsx:1992`(RolesSection 設定檔清單 → 失敗顯示「尚無權限設定檔,請先建立」+ 改綁下拉空選單)、`:1549-1550`(PermissionSetEditor services/operations → 失敗顯示「尚無作業,請先建立」且矩陣區顯示「尚未儲存任何勾選作業」)、`frontend/src/app/(main)/api-clients/page.tsx:918-920`(bindingData/setData → 失敗顯示「尚無綁定的特例權限組」)
- 內容:admin 會照錯誤指示去「重建」已存在的資料,或誤判權限被清空;權限頁「沒有」和「讀不到」的差別直接影響行動。
- 修正:各處取出 `isError` 渲染既有 `<InlineError>`;空狀態文案僅在 `isError===false && data!==undefined` 時顯示(同頁 ServicesOperationsSection/ProfilesSection 已是此寫法,照抄)。
- 首次發現:2026-07-31

#### 🆕 [AD-165] propose-v1.6.1.md 殘留 4 處「11 張」表數字樣(文件債)
- 檔案:`docs/Tasks/v1.6.1/propose-v1.6.1.md:48, 61, 75, 77`
- 內容:tasks-v1.6.1.md 已勘誤 12 張(拆解註記明載),propose 未同步;只讀 propose 者會有表數認知落差。
- 修正:4 處改「12 張」,或文首加勘誤註記指向 tasks 檔。
- 首次發現:2026-07-31

#### ⏸ 遺留 7 項(見前次報告):AD-101(殭屍 run 收殮 — worker/ 零命中)、AD-102(同表併發防疊 — 未做)、AD-103(production compose 帶 adminer,`docker-compose-production.yml:227-235`)、AD-140(api-clients Secret 欄 N+1,`page.tsx:322` 仍逐列)、R-TEST-001(前端零測試;本版 +2,698 行權限矩陣邏輯,痛感升級 🔄)、R-ENV-004(staging/production 兩金鑰仍缺 — **部署 blocker**,grep key 名零命中)、R-ENV-004(本機 .env 缺 14 key)

### 🔵 Low(16 項:13 ⏸ + 3 🆕)

#### 🆕 [AD-155] 預覽同一張表可同時出現 `*` 與具名欄位,優先權未定義
- 檔案:`backend/app/services/effective_permission_service.py:64-74, 167-169`、`backend/app/schemas/client_setting_preview.py:43-49`
- 內容:範圍為 `*` 時 `(table,'*',read)` 與 `(table,'colA',edit)` 都能通過驗證,展開後兩 key 並存;`_higher_action` 不跨 key 比較,契約未說誰優先。今天是預覽 UI 語意曖昧;模組③ 消費端若以 `*` 為準會把 colA 的 edit 降成 read(fail-closed,不外洩)。
- 修正:`effective_permission_service.py:167-169` 收斂 —`*` 存在時剔除動作不高於 `*` 的具名欄位;`client_setting_preview.py:43` 補「並存時具名優先」說明。
- 首次發現:2026-07-31

#### 🆕 [AD-156] 特例組軟刪後,其已過期綁定成為看不到也解不掉的殭屍列
- 檔案:`backend/app/services/client_setting_service.py:1394-1396, 1452-1457`、`backend/app/repositories/client_setting_repo.py:728-747`
- 內容:帶過期綁定的特例組刪得掉(只擋未過期),但 `soft_delete_exception_set` 不動 `client_exception_sets`;事後清單濾掉(看不到)、unbind 因組不存在 404(解不掉)。純資料殘留,不影響權限判斷,量隨時間累積。
- 修正:`client_setting_repo.py:728` 補軟刪該組全部綁定列(此時只可能是過期綁定,不改權限語意)。
- 首次發現:2026-07-31

#### 🆕 [AD-164] 切分頁/改選列時未儲存草稿無聲丟失
- 檔案:`frontend/src/app/(main)/client-settings/page.tsx:2216-2219`(切 tab)、`:1827-1834/:2186-2193`(換列 key 重掛)
- 內容:矩陣一次可能勾上百格、EditorActions 已顯示「有未儲存的變更」,但切 tab/點另一列無攔阻,整批草稿直接消失。
- 修正:三編輯器 dirty 上提,`Segmented onChange` 與 `SimpleEntityTable onSelect` 前檢查,dirty 時 ConfirmDialog 攔一次。
- 首次發現:2026-07-31

#### ⏸ 遺留 13 項:AD-104~108、AD-149(表格按鈕字級,現狀未變,仍待 user 裁定收編或修)、AD-150(semantic english_name TOCTOU — 注意與本次 AD-154 同根因,建議併案)、R-DEP-005/002、R-ENV-004 舊案 ×2、R-LOG-006、CI 群(見前次報告)

### ⚪ Info(3 項)

- 🔄 [reflect 佐證] 測試 module-level `os.environ` 硬覆寫 pattern 第 **6** 批佐證:v1.6.1 五個新測試檔全部 `os.environ["AWS_RDS_*"] = ...`(非 setdefault)強制指向 `data_center_etl_test` — 此慣例保證 `DELETE FROM` 不打真 RDS(安全上正確),但「共用測試 DB 使用約定」reflect 候選權重再 +1,本版不開 AD
- ⏸ [R-AI-001 記錄] 內網資訊面(Arch 文件 CIDR 等)維持不成案存查,本版 Arch 回寫 diff 無新增內網資訊
- ⏸ [07-testing] 測試建 schema 用 create_all 非 alembic(自 2026-07-06;client_setting 測試走冪等 DDL 屬裁定例外)

## 4. 修正優先序

### 立刻(部署前;前四條建議收口窗口一次修畢)
1. 🔴 AD-157 `COLUMN_PAGE_SIZE` 500→200 + isError 顯示(一行級,擋住整個模組可用性)
2. 🟠 AD-158 三處 invalidatesTags 拿掉 `id:'LIST'`(三行,權限畫面失真+靜默斷料)
3. 🟠 AD-151 schema 建置入口 script + 部署 runbook(上站即 500;與 ⏸ R-ENV-004 兩金鑰同屬部署 blocker 清單)
4. 🟠 AD-152 註銷孤兒:RDS 清理 +(至少)解除路徑放行已註銷 client
5. 遺留維持:R-SEC-002/003 + AD-103 adminer(前次「立刻」清單維持)

### 本週(v1.6.1 收口建議)
6. 🟡 前端顯示正確性一批:AD-159(loadFailed 擋整批覆蓋)+ AD-160(跨檔失效)+ AD-163(isError 空狀態)
7. 🟡 對話框行為一批:AD-161(Esc 分流)+ AD-162(Role 指派確認)
8. 🟡 後端一批:AD-153(with_for_update 序列化置換)+ AD-154 最小版(english 表層級 partial unique,與 AD-150 併案)
9. 🟡 AD-165 propose 表數字樣(文件,一分鐘)

### 有空
10. 🔵 AD-155(`*` 收斂)+ AD-156(殭屍綁定清理)+ AD-164(dirty 攔阻)
11. 遺留群:AD-140 N+1、前端測試、CI、env example 舊案等

## 5. 已跳過類別 / 規則與脈絡衝突註記

- `client_setting` 12 表走冪等 DDL 不走 alembic:propose 裁定、比照 semantic_schema 前例 → 不報 R-DB-001/012
- RDS naive timestamp UTC+8(禁 timestamptz):既定裁定(`06-timezone`),12 表全數符合
- 測試連真實本地 PG(5435)非 mock:既定慣例,不報 R-TEST-004/R-BE-022
- 對外封套 vs 後台 `{items,total}` 雙層:前次已確認各自合規,不重報 R-BE-003/011
- 前端單語系繁中:裁定沿用,不套 R-FE-004
- `expires_at` naive 台北 wall-clock 直顯不轉時區:後端契約,不報
- `/client-settings/operations/{uid}/items` 等三層路徑深度超過 `01-routing.md` 建議:task 檔明文指定的路徑形狀,依規格辦理不報(task-004/005 已註記)
- AD-149 字級:v1.6.1 新碼沿用同寫法(`client-settings/page.tsx:385, 915, 1972` 等),屬待裁定案延續,不新開 AD
- `client-settings/page.tsx` 2222 行未拆 components/:已列收口重構候選,不重報(檔內結構性問題已另行檢視)
- `datetime-local` 無 min 可填過去時間:綁定後立即標示「已過期」、後果自曝且後端裁定允許(續期語意),不報
- 允許過去時間綁定 / 續期=先解除再綁 / DELETE role 無指派回 404:task-006 明文設計,內部自洽
- GIT/DEP:9 commit 全合規;零新依賴

## 6. AD-xxx(規則外發現)

本次新增 AD-151~AD-165(見第 3 章)。已巡視無發現的面向:

- **展開演算法核心**:來源配對(開門 ∩ 自家授權再聯集)確實擋住跨來源拼裝;`_effective_columns` 四分支(空範圍/`*`∩`*`/`*`∩具名/具名∩`*`)正確;edit>read 取高正確;軟刪作業/設定檔/特例組自動退出展開
- **權限**:33 管理端點 + effective-permissions 全掛 `require_admin`,member 403 有測試全覆蓋;前端 (main) 三層 RBAC guard 涵蓋 /client-settings,非 admin 不渲染不閃現;非「只前端擋」
- **注入面**:全 SQLAlchemy 參數化;semantic confirmed 查詢 raw SQL 為常值識別字;零字串拼接;DDL 零 DROP
- **稽核**:16 寫入路徑全 `_audit.log`,action ≤43 字元,detail 零機密;順序恆「RDS commit → audit → 失效」
- **快取**:前綴防呆、TTL 強制 >0、全故障降級直讀且 `exc_info` 可觀測、`scan_iter`+500 批 DEL 非 KEYS;失效扇出對照表與 16 條實際呼叫逐條核對一致(含 delete_exception_set 軟刪前取 affected 的順序);`decode_responses=True` 無 bytes 汙染;round-trip 正確
- **併發已正確處理者**:`assign_client_role` 先軟刪再插 + partial unique 兜底轉 409(非 AD-153 聯集型);批次置換單交易原子性;flush 順序不誤觸 unique
- **效期邊界**:讀取端 `> moment` 與 `is_expired` 的 `<= now` 互補無縫;`_normalize_expires_at` 不雙偏移
- **跨 client 越權**:binding_uid 定位有 `api_client_uid != client_uid` 檢核 + 測試
- **效能**:展開路徑批次載入確實被用(無 N+1);小表全撈規模假設成立;v1.6.1 前端無每列一請求(AD-140 為舊案)
- **DB 結構**:12 表 BaseModel 六欄齊、FK 欄全索引、業務唯一鍵全 partial unique(軟刪重建)、action CHECK、跨庫 uid 無 FK
- **前端紀律**:零 any、零原生 alert/confirm、無 localStorage token、`dangerouslySetInnerHTML` 零使用;元件 key 重掛(AD-133 同型)全數在位;in-flight disable 全覆蓋(含逐列 rebinding 鎖);memo/useCallback 齊,大矩陣 re-render 無實際痛感;422/409 後草稿保留正確;範圍縮小殘留項 staleKeys 剔除設計正確(對齊後端 `_within_scope`)
- **測試品質**:548 綠涵蓋 default-closed/∩ 範圍/`*` 展開/取高/效期/快取三情境(含降級注入)/403 全覆蓋/409·422 防呆;**盲區四條**:註銷後 RDS 側狀態(AD-152)、replace_* 併發(AD-153)、語意改名後授權行為(AD-154)、建置入口有人呼叫(AD-151)— 均已開 AD

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **語意層 english_name 的變更管制缺規範**(AD-154/AD-150 實證):confirmed 列的 english_name 已成為權限授權的引用鍵,但語意映射規範無「confirmed 後改名需檢核下游引用」條款,也無唯一性要求 — 升規候選,建議與模組③ 設計一併定案
2. **前後端分頁參數上限無單一來源**(AD-157 實證):`le=200` 只存在於後端 Query 定義,前端硬編碼 500 而 lint/tsc 全綠 — 建議 `02-frontend` 或 API 文件補「分頁上限常數化/契約化」一條
3. **「API 層等價覆蓋」的 UI 手測待補項無 blocker 機制**(AD-157 漏網實證):verification 已誠實記錄「環境受限待補」,但無規則要求待補項在部署/收口前補齊或降級為 blocker — `01-propose`/`99-code-review` 升規候選;R-TEST-001(前端零測試)權重同步 +1
4. **跨庫實體生命週期聯動缺規範**(AD-152 實證):自有 DB 實體(API Client)與 RDS 引用(client_roles 等)無「刪除聯動/孤兒處理」設計準則 — `04-databases` 升規候選(v1.6.1 首次出現跨庫引用,單版本暫記)
5. **部署 runbook 與程式入口的對應缺檢查**(AD-151 實證):新 schema/新 env 這類「上站前一次性動作」散落 verification 殘留節,無 checklist 機制 — 與前次第 7-4 條(verification 回寫)同族,合併升規候選

---

> 本次 🔴1 🟠5 🟡15 🔵16 ⚪3;v1.6.1 新碼 🆕15(🔴1 🟠3 🟡8 🔵3)。**部署本版前必修**:AD-157(前端一行)+ AD-151(建置入口)+ R-ENV-004 兩金鑰(user 自跑);**強烈建議同窗修**:AD-158/152。幫你修 Critical(+🟠 三條)?
