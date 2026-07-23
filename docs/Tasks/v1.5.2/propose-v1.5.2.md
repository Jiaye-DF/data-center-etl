# Propose v1.5.2

## 版本目標

解決來源 ERP 常態性新增欄位造成的兩層斷點:鏡像同步遇到來源新欄位不再整表失敗(目標表自動補欄位,只加不刪),語意映射不再靜默缺列(同步時自動補 confirmed 映射,英文名=原始欄名、中文名取 DS 字典),讓語意 view 與 JSON 查詢在下一輪同步即涵蓋新欄位。價值對象:維運者(不再手動 ADD COLUMN 救同步)、JSON / BI 下游(新欄位即查即用,且中文意義不缺席)。

## In Scope

- **同步 schema drift 偵測 + 目標表自動補欄位**:同步寫入前比對來源 vs 目標欄位差異,目標表缺的欄位自動 `ADD COLUMN`(型別沿用既有來源型別重建規則);**只加不刪**,來源移除 / 改型別的欄位一律不動。
- **語意映射自動補列**:同步收尾時,比對目標 RDS 實體欄位 vs `erp_metadata.semantic_mappings` 既有列,缺列自動補 `status='confirmed'`:`english_name` = 原始欄名小寫(對齊 v1.5.1 unused 命名決議)、`zh_name` = DS 字典中文名(缺則空)、`updated_by` = 系統全零 UUID;表層級列(`column_name=''`)缺者一併補(英文名 = 原始表名小寫),否則 view 無法涵蓋。**既有列(draft / confirmed)一律不覆寫**。
- **別名查重規避**:自動英文名撞同表既有 `english_name` 時以確定性後綴規避,不得讓 view 因別名重複建不起來。
- **同輪生效**:自動補列發生在既有「副本重灌 + view 重生」收尾之前,同一輪同步結束時 view 與 JSON 查詢即含新欄位。

## Out of Scope

- 不處理來源**移除 / 改名 / 改型別**欄位(view / JSON 既有交集機制已靜默容忍;實體欄位退場依規範走兩階段人工流程)。
- 不動鏡像表既有欄位、不做任何 DROP 類操作(底線)。
- 不改人工複核工作流:自動 confirmed 列的正式英文名仍走管理頁改名;改名造成 view 欄名 / JSON key 變動的下游相容處理不在本版。
- 不做映射自動補列的前端新頁面 / 新入口(既有語意映射管理頁即可檢視,`updated_by` 全零 UUID 可辨識系統自動列)。
- 不處理其他既有遺留(殭屍 run、adminer 外露、rate limit 等,見 scan backlog)。

## 對外承諾

- 來源表新增欄位後的**下一輪同步**(增量 / 手動全量皆同):該表同步成功不失敗;目標 RDS 表自動出現新欄位且資料寫入。
- 同輪結束時:`erp_metadata.semantic_mappings` 出現對應 confirmed 列(english=原始欄名小寫、zh=DS 字典、updated_by=全零 UUID);自有 DB 副本同步更新;語意 view 與 `/api/v1/data` JSON 查詢回應含新欄位 key。
- 既有映射列內容(含人工 confirmed / 待複核 draft)前後 diff 不變。
- 無 schema drift 時同步行為與效能與 v1.5.1 一致(偵測不得顯著拖慢既有路徑)。

## 風險與相依

- 技術風險:自動 confirmed 未經人審即進語意層,英文名為原始欄名可讀性低——以 `zh_name` 承載意義緩解;後續人工改正式英文名時 view 欄名(42P16 重建流程可接)與 JSON key 會變,下游若已綁自動 key 會斷,需公告。
- 技術風險:`ADD COLUMN` 型別重建依賴既有 mirror 型別映射;來源特殊型別缺映射時維持既有「該表失敗、不中斷整輪」語意,不得半補欄位。
- 技術風險:多表並行同步同時補映射列,寫入需冪等(PK 衝突不得炸整輪)。
- 第三方依賴:無新增;zh_name 品質依賴 DS 字典覆蓋度。
- 跨團隊阻塞:無。

## 驗收標準

- 後端 `cd backend && uv run pytest` 全綠;`uv run ruff check app tests` + `uv run mypy app` 無新增錯誤。
- 整合驗證(真實或測試 RDS):對來源測試表加一欄 → 觸發同步 → (a) 目標表出現該欄且資料進入;(b) semantic_mappings 出現 confirmed 列(english=小寫原欄名、zh=字典值或空、updated_by=全零);(c) 同輪後該表 view 含新欄位;(d) JSON 查詢回應含新 key。
- 既有映射列(抽 BMA_FILE confirmed 樣本)自動補列前後內容不變。
- 手測:管理頁把自動列英文名改為正式名 → 同步 view → view 欄名更新(42P16 重建路徑正常)。

## 決策記錄

- 2026-07-23:自動補列 `status='confirmed'` 為 **user 裁定**——draft 進不了 JSON 查詢輸出(整欄不出現),無法向下游告知欄位意義;意義由 `zh_name`(DS 字典)承載。
- 2026-07-23:版號 **v1.5.2 為 user 裁定**,比照 v1.5.1 前例(patch 寫 propose 已列 reflect 待決議,不在本版重議)。
- 2026-07-23:表層級映射缺列一併自動補為 AI 拆解時提出的必要配套(無表層級列 view 整表不產生),隨 propose 送 user 複核。
- 程序註記:本 propose 由 AI 依 2026-07-23 對話整理(比照 v1.3.1 / v1.5.1 慣例),user 複核後生效。
