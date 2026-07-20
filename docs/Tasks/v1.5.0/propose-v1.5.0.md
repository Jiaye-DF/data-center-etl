# Propose v1.5.0

> **草稿骨架**:版本目標與 scope 由 user 填寫 / 口述後由 agent 整理;user 認可後才生效(`01-propose/01-propose-format.md`),之後即可跑 `/propose-to-tasks`。

## 版本目標

<1–3 句話。本版本要做什麼。寫「為什麼」+「對誰有價值」,**禁**寫實作細節>

## In Scope

- <條目 1>
- <條目 2>

### 候選：執行期字典擴充（來源＝ERP 字典分析 `docs/ERP-Analyze/mapping-alignment.md` §5，待 user 認可）

- **欄位 comment 缺漏 fallback**：GAQ 缺中文名時退 `DS.GAE_FILE` 畫面標籤（GAQ 缺 191 欄中可補 126 欄）。前置：DMS 複寫加 `GAE_FILE` + 來源帳號授權（`RO_M2201` 現僅被授權 `GAT/GAQ/PAT_FILE`）。
- **資料集頁模組分類**：以 `GAT_FILE.GAT06` 模組代碼分類/篩選資料表（欄位已在現行複寫表內，成本最低）。
- （可選）**表↔ERP 作業對應**：`ZR_FILE` + `GAZ_FILE` 顯示各表由哪支 ERP 作業維護。前置同 GAE（DMS 加表 + 授權）。
- （可選）**`GAU_FILE` 邏輯 PK/FK 關聯展示**：ERP 無實體 FK，此為字典級關聯唯一來源（1,957 列，覆蓋有限）。

## Out of Scope

- <明確排除的功能 / 重構 / 服務>

## 對外承諾

- <user-facing 行為 / API 契約 / 效能指標 / 上線時間>

## 風險與相依

- 技術風險:<...>
- 第三方依賴:<...>
- 跨團隊阻塞:<...>
- **本專案跑法**:改碼後以 `docker compose up -d --build` 驗證(禁 start-dev)。

## 驗收標準

- <可驗證的成功條件;CI green / e2e pass / 手測 case 清單>

## 變更紀錄

- 2026-07-17:建立 v1.5.0 骨架,scope 待 user 決定。
- 2026-07-20:依 ERP 字典分析(docs/ERP-Analyze/)補入「執行期字典擴充」In Scope 候選,待 user 認可。

---

## 背景參考 — 既有待辦候選(非 scope,僅供 user 圈選)

以下為先前版本累積、尚未排入任何版本的候選項目;要納入本版者請移入 In Scope:

- **同步進度條**:任何同步操作要有進度條;執行模型調查與設計方向已完成,待走 propose-to-tasks。順帶修 runs 手動觸發按鈕 404。
- **儀表板 / Header 顯示 SSO 姓名**:`display_name` 欄位已加(e7a101c)但未填入 SSO name,目前仍顯示 email。
- **測試站間歇 502 修法**:輪詢 × 每請求回源 SSO 驗證打爆中央 rate limit(429 被 `df_sso.py` 轉 502);修法待決議(本地 TTL 快取 vs SSO 契約調整)。
- **v1.4.0 遺留**:adminer 外露、rate limit、殭屍 run 清理、750 表同步失敗根因。
- **升規候選 15 條**(260706×8 + 260709×4 + 260710×3)全未決議 — 屬 `/reflect-rules` 決議流程,不必占版本 scope。
- **UI 視覺 3 項人工複測**(v1.4.1 角色回退後):Sidebar admin-only / member 直開 `/users` 導 no-access / 自己那列下拉停用。
