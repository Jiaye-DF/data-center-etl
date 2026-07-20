# reflect-report-260720082922

> 觸發:version-end(v1.5.0 收口)|素材:全版本 fixed.md(v1.0.0×3、v1.1.0×20、v1.4.0×5、v1.4.1×6、v1.5.0×6)|歷史報告:260706/260709/260710(15 條候選全數待決議)

## 候選 1 — 目標 RDS 時間型別規範:一律 naive timestamp(datetime2 等價)+ UTC+8

- **類型**:新增(規範缺漏被實證推翻,事後追認型升規 — 程式已落地,規則待補)
- **來源**:fixed.md `v1.5.0 §3`
- **pattern**:`04-databases/06-timezone.md` 只規範自有 DB 的時間處理,對「目標 RDS 的 DDL 時間型別」零涵蓋;v1.5.0 task-001 因無規則可依,預設用 PG 慣用 `timestamptz` 並已在真實 RDS 落地,隨後被 user 決議推翻(「RDS PG 上只要是時間型別一律 MSSQL datetime2 等價」),需回頭做既有表冪等轉型(`648a092`)。屬「規範被推翻」判準;且此規則影響所有未來在 RDS 自建 DDL 的 task(semantic 層、view、未來任何 etl_meta 類表),不補規則同錯必再犯。
- **建議**:`04-databases/06-timezone.md` 新增段落〈目標 RDS 時間型別〉:「目標 RDS(DMS 下游 PG)上自建 DDL 的時間欄位**一律 `timestamp`(無時區,MSSQL datetime2 等價),禁 `timestamptz`/`timetz`**;值存 UTC+8 naive。DB 端 DEFAULT 必用 `(now() AT TIME ZONE 'Asia/Taipei')`(RDS 系統時鐘為 UTC);應用端寫入前 `to_tw(v).replace(tzinfo=None)`。鏡像/複製流程遇帶時區來源型別,DDL 正規化為無時區、值轉 UTC+8 naive(參考 `app/etl/mirror.py` `_to_naive_tw`)。」
- **影響**:既有 code 已全數合規(`648a092`:semantic_schema 含既有表冪等 ALTER、mirror 型別正規化+值轉換、seed);不破壞 backward(轉型走 `USING` 保資料);需同步 —(a)`docs/Design-Base/README.md` 的 06-timezone 用途描述加「含目標 RDS」;(b)`99-code-review/04-lint-checklist.md` 若列時區檢查項,補 RDS DDL 檢查;(c)grep 驗證:`grep -rn "timestamptz" backend/app backend/scripts` 應僅剩測試模擬舊狀態處。
- **driver**:user(資料平台慣例的 owner)+ 後端 reviewer

---

## 既有待決議候選 — 本版新增佐證(不重列,僅補證據供決議參考)

| 歷史候選 | 本版佐證 | 說明 |
| --- | --- | --- |
| 260706 候選 1 / 260710 候選 1(拆解白名單紀律) | `v1.5.0 §2` | affected_files 誤植不存在檔(schemas/dataset.py)+ 分層必經檔(repo 層)遺漏 — 白名單生成缺「存在性 + 分層必經」驗證,第三個版本出現同類問題,建議決議時納入「拆解時逐一驗證 affected_files 路徑存在 + 依分層規則推導必經檔」 |
| 260706 候選 2(跨 task 介面契約唯一 owner) | `v1.5.0 §6` | 模組篩選的前後端能力契約(distinct 清單/null 篩選)無 owner,前端以「前端聚合+前端過濾」補缺口造成三處一致性問題 |
| 260709 候選 2 / 260710 候選 2(共用測試 DB 使用約定) | `v1.5.0 §1` | module-level `AWS_RDS_*` env 全域覆寫使 FakeSession 測試連上真測試 DB;三個版本持續累積測試環境互踩證據,建議盡快決議 |

## 觀察名單(未達 pattern 門檻,下次 reflect 重評)

1. **附加型背景步驟的失敗語意**(`v1.5.0 §1 + §4`):同版本兩條同類根因 — 附加流程(副本同步、view 重生)的失敗邊界未在設計期定義(graceful 範圍、先毀後建無回退、部分失敗過早記成功狀態)。未跨版本,暫不成案;若 v1.6+ 再現,建議落 `03-backend/03-async-and-tx.md` 或新段〈背景/附加步驟失敗語意〉。
2. **靜態映射查動態實體的漂移防禦**(`v1.5.0 §5`):單條 — 對外查詢組識別字前應驗證存在於實體(白名單本身會過期)。若再現,落 `04-databases/04-sql-safety.md § 漂移面`。

## 已巡視之 pattern 判準(證明跑過)

- 同規則 ≥3 次違反(規範參照分組):本版 6 條規範參照分散(07-testing/02-task-decomposition/06-timezone/04-sql-safety/02-api-and-state/無對應),無單一規則 ≥3 → 無強化候選。
- 同類根因跨 ≥2 版本:拆解白名單(v1.1.0 §7/§10/§12/§17、v1.4.1 §1/§3/§5、v1.5.0 §2)已由歷史候選涵蓋,不重列;其餘見觀察名單。
- 規範矛盾/被推翻:v1.5.0 §3 → 候選 1。
- 規則 ≥6 個月未違反(棄用):專案自 2026-06 啟動未滿 6 個月,全數規則不適用棄用判準,本次跳過。

---

> 本次:候選 1(新增)+ 既有候選佐證 3 組 + 觀察名單 2 條。等 user 決議:✅ 採納開 task(C 段)/ ❌ 拒絕記原因 / 🕐 暫緩下次重評。另提醒:歷史 15 條候選已跨 3 份報告待決議,其中「拆解白名單紀律」「共用測試 DB 約定」兩組已三度累積佐證,建議優先排入決議。
