# DS 字典 ↔ 本專案 mapping 對照與驗證

> 依據：`output/erp-metadata.md`（2026-07-17 產出，Oracle `toptest` 實查）與 `data/*.tsv` 原始 dump。
> 驗證方式：**靜態比對**（本專案程式碼假設 vs 分析報告事實），未連線任何 DB。驗證日期 2026-07-20。

## 1. 本專案 mapping 現況盤點

| 元件 | 角色 | 狀態 |
| --- | --- | --- |
| `backend/app/etl/dictionary.py` | **正式管線的中文名來源**：執行期對 source RDS 查 `DS.GAT_FILE`（表中文名）/ `DS.GAQ_FILE`（欄中文名），繁體(`'0'`)優先、缺退簡體(`'2'`) | ✅ 現行使用 |
| `backend/app/etl/mirror.py` | 同步時逐表呼叫 `fetch_table_comment` / `fetch_column_comments`，組 `COMMENT ON TABLE / COLUMN` 寫入目標庫（無對應者略過，不 raise） | ✅ 現行使用 |
| `backend/app/services/snapshot_service.py` | refresh 全量內省時呼叫 `fetch_table_comments` 批量取表中文名進快照 | ✅ 現行使用 |
| `etl/config/mapping/ds.yaml` / `m2201.yaml` | v1.0.0 Glue 路線的欄位對照 yaml | ⚠️ **佔位假資料**，config-ETL 路線已於 v1.3.1 下線（見 §4） |

前提：`dictionary.py` 查的是 **DMS 複寫後的 RDS PG**（`"DS"."GAT_FILE"` 等引號識別字）。字典查得到的先決條件是 **DMS 任務有把 `DS.GAT_FILE` / `DS.GAQ_FILE` 納入複寫範圍**；缺表時模組 graceful 回空（comment 從缺、不中斷同步）。

## 2. 逐項驗證：`dictionary.py` 結構假設 vs 分析事實

| # | 程式假設（`dictionary.py`） | 分析事實（出處：`erp-metadata.md`） | 結論 |
| --- | --- | --- | --- |
| 1 | 字典 schema = `DS` | 全域字典放在 `DS` schema（§0、§3.1） | ✅ 一致 |
| 2 | 表中文名字典 = `GAT_FILE`，`GAT01`=表名 / `GAT02`=語別 / `GAT03`=中文名 | §2 條件 2 **成立**：`GAT01`=表名(小寫)、`GAT02`=語言別、`GAT03`=表中文名；另有 `GAT06`=模組代碼（程式未用，見 §5） | ✅ 一致 |
| 3 | 欄中文名字典 = `GAQ_FILE`，`GAQ01`=欄名 / `GAQ02`=語別 / `GAQ03`=中文名 | §2 條件 3：欄位字典即 **`DS.GAQ_FILE`**（無 `GAT_ITEM`），`GAQ01`=欄位名(小寫)、`GAQ03`=欄位中文名；另有 `GAQ04/05`=說明/選項（程式未用） | ✅ 一致 |
| 4 | 語別代碼 `'0'`=繁體、`'2'`=簡體，繁優先缺退簡 | §2 條件 2 實查確認 **0=繁體、2=简体**；`GAT_FILE` 共 4,857 列（繁體 2,430）、`GAQ_FILE` 繁體 54,196 列 | ✅ 一致 |
| 5 | 以 `lower()` 比對表名/欄名（查詢鍵先 `.lower()`） | 字典值本身即**小寫**存放（`GAT01`/`GAQ01` 皆小寫，§2）；程式兩側都套 `lower()`，大小寫皆安全 | ✅ 一致 |
| 6 | 字典表缺失 graceful 回空（不 raise） | 設計決策（v1.2 comment 放寬），與分析無衝突；對應 DMS 未複寫字典表時的行為 | ✅ 無衝突 |

**結論：正式管線的字典結構假設與 ERP 實查事實完全一致，無需修改程式。**

## 3. 覆蓋率與缺口（M2201 有資料的 333 張表，數據由 `data/*.tsv` 計算）

| 項目 | 數字 | 說明 |
| --- | --- | --- |
| 欄位總數 | 11,947 | `m2201_columns.tsv` |
| GAQ 欄中文名覆蓋 | 11,756（98.4%） | 現行 `dictionary.py` 可取得 |
| GAQ 缺漏欄位 | **191** | comment 從缺（mirror 略過該欄） |
| ↳ 其中 GAE 畫面標籤可補 | **126**（66%） | `m2201_column_screen_labels.tsv` 比對；剩 65 欄兩者皆無 |
| GAE 畫面標籤總覆蓋 | 8,803 欄 | 亦可作欄位「使用者慣用名」補充語意 |
| 表中文名（GAT）缺漏 | 20 / 333 | 多為暫存/客製表（`TT10…`、`TC_*`、`BM*`），屬合理缺漏 |

## 4. 佔位 yaml 與事實差異（僅標註，不修）

`etl/config/mapping/ds.yaml`、`m2201.yaml` 為 v1.0.0 Glue 骨架的「合理代表性佔位」，**config-ETL 路線已於 v1.3.1 下線**（API/service/repo 已刪，model 保留），故僅記錄差異、不回頭修正：

- `ds.yaml` 把 `GAT_FILE` 寫成業務單據表（`GAT_NO`/`GAT_DATE`/`GAT_QTY`…）——實際 `GAT_FILE` 是**字典表**，欄位為 `GAT01~GAT06`；`GAQ_FILE`、`GAM_FILE` 同為虛構欄位。
- `m2201.yaml` 把 `M2201` 當成單一目標表——實際 `M2201` 是**公司帳套 schema**（2,283 張表），非單表。
- 若未來重啟 Glue/批次路線，欄位對照應改由 `DS.GAT_FILE`/`GAQ_FILE` 字典或本目錄 `data/*.tsv` 產生，勿沿用佔位內容。

## 5. 可用而未用的字典資源（→ v1.5.0 propose 候選）

| 資源 | 內容 | 對本專案的用途 | 實作注意 |
| --- | --- | --- | --- |
| `GAT_FILE.GAT06` | 表所屬模組代碼（如 `AOO`/`ASM`） | 資料集頁可按 ERP 模組分類/篩選 | 已在現行複寫表內，**成本最低** |
| `DS.GAE_FILE` | 畫面欄位標籤 158,187 列（`GAE01`=畫面 / `GAE02`=欄位 / `GAE03`=語別 / `GAE04`=標籤） | 欄 comment fallback：GAQ 缺的 191 欄可補 126 欄 | `RO_M2201` 於 DS **僅被授權 `GAT/GAQ/PAT_FILE`**（§2 條件 3）；需 DMS 加表 + 來源授權才可用 |
| `DS.ZR_FILE` + `GAZ_FILE`/`ZZ_FILE` | 程式↔表關連（102,262 列）與程式中文名 | 顯示「這張表由哪支 ERP 作業維護」，幫助使用者辨識資料集 | 同上，需 DMS 加表 + 授權 |
| `DS.GAU_FILE` | 鼎新邏輯層 PK/FK（1,957 列） | ERP **無任何實體 FK**（§2 條件 4），此為表間關聯的唯一字典級來源 | 同上；覆蓋有限，關聯仍以命名慣例推導為主 |

上述已列入 `docs/Tasks/v1.5.0/propose-v1.5.0.md` In Scope 候選，待 user 認可後走 `/propose-to-tasks`。
