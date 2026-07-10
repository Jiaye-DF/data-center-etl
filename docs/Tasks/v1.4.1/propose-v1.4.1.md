# Propose v1.4.1

> **草稿**:由 agent 依 user 口述整理,propose 由 user 認可後才生效(`01-propose/01-propose-format.md`);確認 / 修改後即可跑 `/propose-to-tasks`。
> 決議點見〈風險與相依〉,認可前請先拍板。

## 版本目標

把「角色」從 `users` 表的字串欄位獨立為一等實體(`roles` 表),成為全系統角色的唯一事實來源。本版**不改變任何授權行為**(admin 可寫 / viewer 唯讀語意沿用),重點是結構收斂 + 讓 admin 能在系統內指派使用者角色(現況只能手動改 DB)——為後續版本整合 DataHub 的 API 權限(哪些角色可讀取 / 使用哪些資料 API)建立地基。

## In Scope

- **新增 `roles` 表**:角色代碼(唯一)、顯示名稱、描述、系統內建標記;seed 內建 `admin` / `viewer` 兩筆(系統內建角色禁刪、禁改代碼);軟刪除等基底欄位沿用既有 model 慣例。
- **`users` 改以外鍵關聯 `roles`**:加關聯欄位並 migration backfill 既有使用者(依現行 `role` 字串值對應);既有 `users.role` 字串欄位與 `ck_users_role` 約束**保留、標記 deprecated**(禁 DROP,實體移除走人工移除清單)。
- **授權鏈路改由角色表驅動**:守衛(`require_role` / `require_admin`)、`/auth/me` 與 SSO me 回應的 `role` 欄位改自關聯角色取值;對外值與行為**完全不變**(admin 可寫、viewer 呼叫寫入 API 403、SSO 首次登入預設 viewer)。
- **角色列表後端 API**(已登入可讀):供前端下拉與後續權限整合使用。
- **使用者角色指派(admin only)**:使用者清單(帳號 / 顯示名稱 / 登入來源 / 角色)+ 指派角色動作;UI **併入既有頁面體系**(不為此開多個新頁,對齊「別過度拆成新頁」原則);admin 不可把自己降級(避免鎖死無 admin)。
- **稽核**:角色指派動作寫入既有稽核紀錄機制。

## Out of Scope

- **DataHub API 權限矩陣本體**:role ↔ API 資源的映射表、端點級 enforcement、權限管理 UI——屬未來版本(本版只把角色實體化,不預先設計權限結構)。
- **自訂角色 CRUD**:本版僅內建 admin / viewer;新增自訂角色留待權限矩陣版一併設計(見決議點 2)。
- **SSO 中央角色同步**:角色仍以自有 `users` / `roles` 表為準,不從 DF-SSO 中央帶入。
- **實體 DROP `users.role` 欄位 / 約束**:一律不由本版程式或 migration 執行,列人工移除清單。
- **細粒度資料級權限**(schema / 表級可見性):未來與 API 權限一併規劃。

## 對外承諾

- 既有授權行為**零變化**:admin 可寫、viewer 唯讀(寫入類 API 403)、SSO 首次登入為 viewer;`/auth/me` 回應的 `role` 欄位名與值格式不變,前端無感。
- `roles` 表成為角色唯一事實來源;migration 後既有使用者全數對應到內建角色,無 orphan。
- admin 可在系統內查看使用者清單並指派角色,改動**即時生效**(下一個請求即以新角色判定),不需重新登入。
- 全程無任何 DROP migration;deprecated 結構附人工移除清單。

## 風險與相依

- **決議點 1 — 使用者角色指派 UI 是否入本版**:上方已列入 In Scope(理由:「未來分別要給哪些人讀取使用」,先要有「指派誰是什麼角色」的能力,現況只能改 DB);若 user 決定本版純結構、UI 留到權限矩陣版,刪除該條目即可。
- **決議點 2 — 自訂角色**:本版僅 seed admin / viewer。若 DataHub 權限整合前就需要第三種角色(例如「API 使用者」),可提前於本版開放角色 CRUD,請明示。
- **角色即時生效的前提**:守衛每請求自 DB 讀 user(SSO 來源另回源中央),角色不嵌在 JWT 內——指派後即時生效,無舊 token 殘留問題;此行為需在測試中固定住。
- **migration 順序**:backfill 需在同一 migration 內完成(建表 → seed → 加欄 → backfill),避免「有 user 無角色」中間態;失敗需可重跑。
- **降級鎖死**:admin 把唯一 admin(含自己)降級會導致系統無管理員;需最小防呆(至少禁止自降)。
- **與 hotfix 的分支關係**:本版為 feature,自 `main` 開分支;與 SSO 429 / uvicorn workers 等部署 hotfix 互不阻塞。
- **本專案跑法**:改碼後以 `docker compose up -d --build` 驗證(禁 start-dev)。

## 驗收標準

- 跑 migration 後:`roles` 表存在且有 `admin` / `viewer` 兩筆 seed;既有 `users` 全數帶關聯角色(SQL 驗證無 NULL);`users.role` 舊欄位原樣保留。
- `cd backend && uv run pytest` 全綠,含:viewer 呼叫寫入類 API 回 403、admin 回 2xx、SSO 首次登入建立之使用者角色為 viewer、角色指派後下一請求即以新角色判定、admin 自降級被拒。
- `curl /api/v1/auth/me`(admin / viewer 各一)回應之 `role` 值與 v1.4.0 完全一致。
- admin 於 UI 將某使用者 viewer ↔ admin 互換,重新整理後該使用者權限即時反映;角色指派動作可在稽核紀錄查到。
- `cd frontend && npm run typecheck && npm run lint && npm run build` 全綠;localhost `docker compose up -d --build` 全流程可跑。
- 文件附人工移除清單(`users.role` 欄位 + `ck_users_role` 約束);repo 內無任何 DROP migration。

## 變更紀錄

- 2026-07-10:由 user 口述整理成 v1.4.1 草稿。動機:role 目前是 `users` 表字串欄位,無法承載後續 DataHub API 權限整合(哪些角色可讀取 / 使用哪些 API);先把角色實體化為 `roles` 表並提供角色指派能力,權限矩陣留待未來版本。

---

## 背景參考(非 scope,供拆 task 對照)

- **現況**:`users.role` 為 `String(20)` + `CheckConstraint("role IN ('admin','viewer')")`(`backend/app/models/user.py:23-37`);守衛 `require_role(*roles)` 字串比對(`backend/app/api/deps.py:96-106`);`/auth/me` 與 SSO me 回應直接回 `user.role`;角色以自有表為準、SSO 不帶角色(`backend/app/api/v1/sso.py:45`)。
- **無既有管理面**:全系統無使用者清單 / 角色管理 UI 與 API,改角色目前僅能手動改 DB。
- **未來方向(僅供對齊,不入本版)**:DataHub 對外資料 API 上線後,以 role ↔ API 資源建立讀取 / 使用權限矩陣;屆時再設計 `permissions` / `role_permissions` 等結構與管理 UI,並沿用本版 `roles` 表為主體。
