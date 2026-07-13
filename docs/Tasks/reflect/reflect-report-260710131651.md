# reflect-report-260710131651

> **trigger**:version-end(v1.4.1 五 task 完成,收口中)
> **素材**:`docs/Tasks/v1.4.1/fixed.md`(§1–§6,全數為本版 multi-agent 執行期間即時寫入);對照 `v1.0.0`(§1–§3)、`v1.1.0`(§1–§19)、`v1.4.0`(§1–§5)確認跨版本同型。
> **歷史報告**:`reflect-report-260706093400.md`(8 候選)、`reflect-report-260709132015.md`(4 候選)— **12 條全數尚未決議**(無 ✅/❌/🕐 記錄),依規則不重列、不重評;本報告僅收 v1.4.1 新素材,與未決議候選同檔落腳者於「影響」欄註明 C 段合併建議。
> **性質**:僅 B 段反思,未動任何 `docs/Design-Base/*`;C 段升級待 user 逐條決議。

---

## 摘要

共 **3 個候選**:強化 2 / 新增 1 / 修正 0 / 棄用 0。

| # | 主題 | 類型 | 來源 |
| --- | --- | --- | --- |
| 1 | 拆解層「白名單 × 規格演進」同步紀律(時序相依 / 中途補段 / fixed「後續」核對) | 強化 | v1.4.1 §1、§3、§5 |
| 2 | 共用測試 DB 的 schema / seed 同步約定 | 新增 | v1.4.1 §2、§4 |
| 3 | Acceptance 驗證指令對照 binding 規範的一致性檢查 | 強化 | v1.4.1 §6 |

---

## 候選 1 — 拆解層「白名單 × 規格演進」同步紀律

- **類型**:強化(既有規則太弱:`03-multi-agent-flow.md` 白名單協議只管「執行期不互踩」,完全未管「白名單隨規格演進的維護責任」)
- **來源**:fixed.md `v1.4.1 §1`、`v1.4.1 §3`、`v1.4.1 §5`(同版本內同類根因 **3 連發**,且 §5 明文記錄為「第三次同型態問題」)
- **pattern**:三條的根因同源 — **task 白名單是拆解當下的快照,但規格是活的**,三種演進路徑全都讓白名單失效:
  1. §1「時序相依未察覺」:001 的 Acceptance(收 NOT NULL)依賴 002 才落地的寫入路徑,地基 task 無法獨立滿足自己的驗收 → 規格內部時序矛盾;
  2. §3「中途補段未重掃」:orchestrator 為 002 補 v8 規格時,未盤點「固定即將被終結之過渡態的既有測試」,worker 被迫白名單外最小修正;
  3. §5「fixed『後續』未核對」:§3 已明文預告 task-003 需連動 `test_models_v141.py`,但 003 規格 / 白名單撰寫時未回頭讀 fixed.md,同樣的白名單外修正再演一次。
  三次的收場一模一樣(白名單外最小修正 + 補一條 fixed.md),證明這不是個別疏忽而是協議缺一塊:**沒有任何規則要求在「規格變更 / 接手 task 撰寫」時重新驗證白名單的完整性**。
- **建議**:兩檔各補一段(同一 C 段 task 處理):
  1. `01-propose/02-task-decomposition.md § 拆解原則` 補「**約束時序檢查**」條:「task 的 Acceptance 若依賴後續 task 才落地的寫入 / 讀取路徑(如收緊 DB 約束需所有寫入方先改),該驗收條件**必**移至依賴鏈上『前提成立的那個 task』,禁要求地基 task 提前收緊(v1.4.1 §1 案例:NOT NULL 收緊應直接排在寫入路徑 task,而非建欄 task)」。
  2. `01-propose/03-multi-agent-flow.md § 衝突偵測` 後補「**白名單維護**」節:「(a) task 規格於拆解後變更(orchestrator 補段 / 改 Acceptance)→ `affected_files` 必同步重掃,特別盤點『固定被變更行為的既有測試檔』;(b) worker / orchestrator 撰寫或修訂任一 task 規格前,必讀本版 fixed.md 既有條目的『後續』欄,其中點名的連動檔一律納入該 task 白名單;(c) worker 遇白名單外硬衝突 → 停手回報 orchestrator 擴白名單,禁自行『最小修正』後補記(v1.4.1 三次實戰均為後者,靠 worker 自律收場,不可依賴)」。
- **影響**:不破壞 backward(純流程規範);v1.4.1 三次事故均已閉環(修正都已進 commit 且測試綠)。需改檔:`01-propose/02-task-decomposition.md` + `01-propose/03-multi-agent-flow.md` — 與**未決議**的 260706 候選 1(連動檔盤點)、260709 候選 1(工作樹紀律)完全同檔,強烈建議 C 段併同一 task 一次改齊(三份報告對這兩檔的補強面向不重疊:連動盤點 / git 紀律 / 白名單維護)。checklist 同步:無機械驗證點。
- **driver**:user(df.it.all,規範 owner)review;C 段建議由 orchestrator 角色 agent 執行(三次事故皆發生在其派工 session,第一手脈絡在其側)

## 候選 2 — 共用測試 DB 的 schema / seed 同步約定

- **類型**:新增(`03-backend/07-testing.md` 無任何「測試 DB 生命週期」規範;與未決議之 260709 候選 2「並行使用約定」同檔但**面向不同** — 該候選管多 worker 互踩,本候選管單執行者也會踩的 schema/seed 漂移)
- **來源**:fixed.md `v1.4.1 §2`、`v1.4.1 §4`(同版本 2 條同源);跨版本佐證:`v1.4.0 §5` 同屬「測試 DB 無人負責」家族(該條已由 260709 候選 2 立案,不重複計入本候選次數)
- **pattern**:共用測試 DB(`data_center_etl_test`)由多支測試檔以 `create_all` 各自「順手」建 schema,但 **`create_all` 對已存在的表不補欄位、也不 seed migration 才會種的地基資料** — 於是每次 model 加欄(§2:`role_pid` 加欄後 `UndefinedColumnError` 炸 5+ 檔)或新增 migration-seeded 前提(§4:`create()` fail-fast 依賴 roles seed,全新環境按字母序先跑 `test_audit_log.py` 即集體炸)都會重演。§2 根因欄明言:「沒有單一檔案『擁有』該 DB、也沒人負責在 schema 演進時補丁」— 責任真空是結構性的,隨每個加欄 / 加 seed 的版本必然復發。
- **建議**:`03-backend/07-testing.md` 新增「**共用測試 DB 生命週期**」節:
  1. 共用測試 DB 的 schema 對齊責任收斂到**單一 session-scope autouse fixture**(置於 `tests/conftest.py`):對 model 新增欄位跑純新增 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`(禁 DROP),對 migration-seeded 地基資料(如 roles)跑冪等 seed — v1.4.1 已落地的 `_seed_shared_test_db_roles`(`backend/tests/conftest.py`)即後者範本,升規後將 schema-sync 一併收入同 fixture;
  2. 明定「新增 mapped column 或 migration seed 的 task,`affected_files` **必**含 `tests/conftest.py` 同步該 fixture」(與候選 1 的白名單維護條互相呼應);
  3. 註明 CI / 全新環境不受影響(首次 `create_all` 即最新 schema),本約定為本機長壽 DB 專用。
- **影響**:不破壞 backward — §2 的本機修補與 §4 的 conftest seed 已落地,升規等於把既成解法制度化;既有測試檔零改動(fixture 中央化,各檔不必自帶補丁)。需改檔:`03-backend/07-testing.md`(主)— 與未決議 260709 候選 2 同檔同節區,強烈建議 C 段併同一 task(「並行約定」+「生命週期」一次補齊 07-testing.md)。checklist 同步:`99-code-review/03-pr-self-check.md` 若列 schema 變更項,加「conftest schema-sync fixture 已同步」一條。
- **driver**:user(df.it.all)review;C 段可由後端 area agent 執行(解法在 v1.4.1 conftest 已有半成品)

## 候選 3 — Acceptance 驗證指令對照 binding 規範的一致性檢查

- **類型**:強化(`02-task-decomposition.md § Acceptance 寫法` 只要求「機械可驗」,未要求「指令本身合規」)
- **來源**:fixed.md `v1.4.1 §6`
- **pattern**:單版單條,但屬「拆解產物品質無守門機制」的協議層缺口(立案基準比照 260709 候選 1/2 之先例)— orchestrator 手寫的 Acceptance 逐字指令(`jq '.data[].code'`)假設 `data` 為裸陣列,直接違反 binding 的 `01-routing.md`「禁 data 直接為 array」;同一份 task 檔內規格段(要求列表)與驗收段(假設裸陣列)自相矛盾而拆解時無人核對。Worker 依 CLAUDE.md 規範優先序正確裁決(規範 > task 字面),但每次裁決都消耗一輪「發現矛盾 → 查優先序 → 記 fixed.md」;指令若被逐字執行,驗證結果是**靜默 false 而非炸錯**(jq 對 dict 取 `.data[]` 回空),誤判風險高。
- **建議**:強化 `01-propose/02-task-decomposition.md § Acceptance 寫法`:
  1. 補一條:「驗證指令涉 API 回應結構(jq path / curl 斷言)→ 撰寫時**必**對照 `03-backend/01-routing.md` 回應外殼慣例(`data` 為 dict,列表為 `{items: [...]}`);列表類驗證一律寫 `.data.items[]`,禁 `.data[]`」;
  2. 該節既有範例若含回應斷言,同步改為合規外殼路徑(杜絕範例被逐字複製)。
- **影響**:不破壞 backward(v1.4.1 §6 已依規範優先序落地,實作合規、僅指令字面偏離);需改檔:`01-propose/02-task-decomposition.md` — 又與候選 1 同檔,C 段同一 task 順手處理(一檔三補:約束時序 / Acceptance 合規 / 連動盤點)。checklist 同步:無。
- **driver**:user(df.it.all)review;C 段由 orchestrator 角色 agent 執行(錯誤源頭即拆解層,由其修最對症)

---

## 已巡視、未成案素材(寧空勿湊聲明)

四條 pattern 判準已套用於 v1.4.1 §1–§6 全量素材(對照 v1.0.0 / v1.1.0 / v1.4.0 全歷史):

- **§1–§6 全數入案**(§1/§3/§5 → 候選 1;§2/§4 → 候選 2;§6 → 候選 3),本版無去噪淘汰條目 — 六條皆為系統性根因,無 typo / 個別失誤層級素材。
- **同規則 ≥ 3 次違反(強化判準)**:候選 1 即此判準成立的首例(同版本內三次同型,§5 自證「第三次」)。
- **棄用候選 = 0**:fixed 素材時間窗(2026-07 起)仍不足 6 個月,無法判定「長期未違反」;下次 reflect 再評。
- **規範矛盾(修正判準)**:v1.4.1 無新增跨檔規則衝突(§6 為 task 產物與規範衝突,非規範互相矛盾,已依優先序解)。
- **前次 12 候選**:全數未決議,依規則不重列;scan 報告(260710131118 第 7 章)第 2、3 點與本報告候選 1、3 互為佐證,決議時可對照。

---

> 本報告 3 個候選(強化 2 / 新增 1)。連同前兩份未決議 12 候選,累計 **15 條**等 user 決議:✅ 採納 → 開 C 段升級 task;❌ 拒絕 → 於報告條目下記原因;🕐 暫緩 → 下次重評。
> **落腳檔高度集中,C 段合併建議**:`01-propose/02-task-decomposition.md` + `03-multi-agent-flow.md`(本報告候選 1、3 + 260706 候選 1 + 260709 候選 1)可併一個 task;`03-backend/07-testing.md`(本報告候選 2 + 260709 候選 2)併一個 task — 兩個 C 段 task 即可消化 15 條中的 7 條。
