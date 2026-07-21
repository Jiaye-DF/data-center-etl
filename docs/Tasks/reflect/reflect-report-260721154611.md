# reflect-report-260721154611

> 觸發:version-end(v1.5.1 收口)|素材:全版本 fixed.md(v1.0.0×3、v1.1.0×20、v1.4.0×5、v1.4.1×6、v1.5.0×6、**v1.5.1×4**)|歷史報告:260706/260709/260710/260720(累計 16 條候選全數待決議)
> 補充素材:`Issue-Scan-Project-260721145815.md`(v1.5.1 scan,AD-119~132)、`propose-v1.5.1.md § 決策記錄`(規範被推翻之裁定紀錄)

## 候選 1 — 並行執行與背景狀態安全:互斥、進度 key 命名、失敗語意、行程死亡收殮(觀察名單升格)

- **類型**:新增
- **來源**:fixed.md `v1.5.1 §2`(worker SIGKILL 後 run 卡 running,無人收殮)、`v1.5.1 §4`(多表並行搶建 schema 撞 pg_namespace,CREATE SCHEMA IF NOT EXISTS 非併發安全)、`v1.5.0 §1`(副本同步波及)、`v1.5.0 §4`(view 失敗語意 — 部分失敗過早記成功);佐證:scan `AD-119`(進度 key 落他人 delete_pattern blast radius)、`AD-120`(手動/排程共用流程無互斥)、`AD-101/AD-102`(v1.4.0 起遺留:殭屍 run / 同表並發)
- **pattern**:260720 觀察名單第 1 條(「附加型背景步驟的失敗語意」,當時單版本暫不成案)於 v1.5.1 **再現且擴大**:同一根因家族(並行化 / 背景化之後,共享狀態的生命週期與互斥從未被設計)在兩個版本內累積 4 條 fixed + 4 條 scan 發現 — 具體缺口四類:(a) 跨 process 共用流程無互斥(§4 race、AD-120);(b) Redis 進度 / 鎖 key 無命名隔離約定,落入他人 `delete_pattern` 範圍(AD-119,諷刺的是 APPLY_PROGRESS_KEY 註解已識別過同型 hazard);(c) 部分失敗的成功語意(v1.5.0 §4 簽名過早寫入);(d) 行程死亡後的狀態收殮(§2 SIGKILL 殭屍 run,個案收殮、治本仍缺)。跨 ≥2 版本、同類根因、無對應規則 → 成案。
- **建議**:`03-backend/03-async-and-tx.md` 新增段〈並行與背景執行安全〉,四條規則:(1) **跨 process 可能併發的共用流程**(API + worker、多 worker)必以 Redis `SET NX`(帶 TTL)或 PG advisory lock 互斥,或明確設計為可容忍(如 SAVEPOINT 吞併發 DDL 衝突 — `mirror.py` write_mirror 為範例);(2) **Redis 進度 / 鎖 key 一律獨立 namespace**(`<feature>-progress:*` / `<feature>-lock:*`),禁落入任何既有 `delete_pattern` 樣式範圍,新增 key 時 grep 全部 `delete_pattern` 呼叫點驗證;(3) **多步驟背景流程**僅在全部成功後寫入「已完成」狀態(簽名 / 基準值),部分失敗須可重試(參照 view_generator「全成功才寫簽名」);(4) **長生命週期狀態**(run 狀態、進度 key)必有行程死亡後的收斂機制 — TTL 兜底或啟動時收殮(殭屍 run watchdog 即此條的補洞 task,建議 v1.5.2 實作)。
- **影響**:既有 code 於 v1.5.1 收口修正後全數合規((1) AD-120 SET NX 已落地、(2) AD-119 已換 namespace、(3) v1.5.0 已修、(4) 唯一缺口 = 殭屍 run 治本,列補洞 task 不擋升規);不破壞 backward(規範該 commit 之後的新碼);需同步 — `99-code-review/04-lint-checklist.md` 若有併發檢查段補「新增 Redis key 對照 delete_pattern 樣式」一條;`docs/Prompts/scan-project.md § 心法 1` 的巡視面向補「DDL / 共享狀態併發安全」(v1.4.0/v1.5.0 兩次 scan 均未涵蓋此面向,AD-132 遲至 user 實錘才發現)。
- **driver**:user + 後端 reviewer

## 候選 2 — 必備欄位檢查從「存在」強化為「存在 + 型別」(scan 工具盲區)

- **類型**:強化
- **來源**:fixed.md `v1.5.1 §3`(semantic_mappings `updated_by` 建成 text,值混雜工具標記,與 `04-databases/00-overview.md`「updated_by = UUID」不符;**雙重漏網**:拆解自行具體化 + v1.5.0 scan 未比對型別,遲至 user 查 RDS 才發現並需冪等轉型 + alembic 補救)
- **pattern**:嚴格計數僅 1 條,未達「同規則 ≥3 次違反」門檻;列為候選的理由:(a) fixed.md §3 已明載此為升規候選(user 認可的工具盲區);(b) 這是**檢查工具本身的結構性盲區**而非個案失誤 — R-DB-002 只驗「欄位存在」,型別偏離永遠掃不到,同錯必然無法由現行 scan 攔截;(c) 補救成本實證偏高(RDS 冪等轉型 + 副本 alembic + 5 檔連動)。
- **建議**:`docs/Prompts/scan-project.md § E. DB` 的 **R-DB-002** 由「缺必備欄位 🟡」擴充為「缺必備欄位**或型別偏離** 🟡 — `uid`/`created_by`/`updated_by` 必 UUID、`created_at`/`updated_at` 必依 06-timezone 型別、`is_deleted` 必 boolean;比對基準 `04-databases/00-overview.md`」;同步在 `99-code-review/04-lint-checklist.md` DB 段補一條「新表 DDL 對照必備欄位型別」。
- **影響**:既有表於 `648a092` + `v152` 修正後全數合規,無 grandfather 負擔;不破壞 backward;僅改 prompt / checklist,不動 Design-Base 規則本文(`04-databases/00-overview.md` 已載明型別,問題在檢查端沒對照)。
- **driver**:user(裁定人)+ DB reviewer

## 候選 3 — `05-version-bump`:patch 版本開 propose 的流程修正(規範被推翻)

- **類型**:修正
- **來源**:`propose-v1.5.1.md § 決策記錄`(2026-07-21:「版號 v1.5.1 為 user 裁定,推翻 05-version-bump『新功能走 minor / patch 不寫 propose』規範;是否更新規範檔待 /reflect-rules 決議」)。註:本候選來源為 propose 裁定紀錄而非 fixed.md — 規範被推翻發生在流程層(無 code 修正條目可鏈),屬 `07-rule-evolution` 判準第三條(規範矛盾 / 被推翻)的裁定型實證,依 260720 候選 1(同為事後追認型)慣例列案。
- **pattern**:v1.5.1 實際內容 = 收尾補強 + 小型新功能(管理頁),user 判斷用 patch 版號 + 完整 propose/tasks 流程最合理;現行規範二分法(「新功能必 minor」「patch 不寫 propose」)與實務衝突 — 規範被推翻判準成立。
- **建議**:`01-propose/05-version-bump.md` 修正版號判準:版號層級(major/minor/patch)依**變更幅度與相容性**判定,**流程重量(是否開 propose/tasks)依變更風險與範圍**判定,兩者脫鉤 — 補一條「patch 版本若含任何新功能面(UI 頁面 / API 端點)或跨 task 拆解需求,仍走完整 propose → tasks 流程;純 hotfix 才可免 propose」。
- **影響**:v1.5.1 即先例(grandfather 不需處理);不破壞 backward;需同步 `01-propose/00-overview.md` 若有版號流程描述、`README.md` 的 05-version-bump 用途一句話。
- **driver**:user(流程 owner)

---

## 既有待決議候選 — 本版新增佐證(不重列,僅補證據供決議參考)

| 歷史候選 | 本版佐證 | 說明 |
| --- | --- | --- |
| 260706 候選 1 / 260710 候選 1(拆解白名單 / 拆解紀律) | fixed.md `v1.5.1 §3` | **第 4 個版本出現同類問題**:propose 只寫「欄位含 updated_by」未指定型別,拆解階段自行具體化為 text(未回查 `04-databases/00-overview.md` 規範地板),實作照拆解檔執行 — 建議決議時在拆解紀律候選內納入「propose 未指定的規格,拆解須回查 Design-Base 地板,禁自行發明」子條 |
| 260709 候選 2 / 260710 候選 2(共用測試 DB 使用約定) | scan `260721145815 § ⚪`(輔助佐證) | 新增測試檔再度複製 module-level `os.environ` 硬覆寫 pattern(`test_semantic_mappings_api.py` / `test_snapshot_refresh_progress.py`),第 4 度累積;pattern 持續擴散、收斂成本遞增,建議本輪一併決議 |
| 260720 候選 1(RDS 時間型別 → `06-timezone`) | fixed.md `v1.5.1 §2`(輔助) | 殭屍 run 收殮時 `finished_at` 依通則寫 UTC+8 naive — 通則已被日常遵循,僅剩規範檔未補,建議儘速採納收掉 |

## 觀察名單(未達 pattern 門檻,下次 reflect 重評)

1. **靜態映射查動態實體的漂移防禦**(260720 觀察 2 保留):v1.5.1 無新事證,維持觀察。
2. **系統自建物件對既有內省 / 掃描視圖的汙染**(新,fixed.md `v1.5.1 §1`):在目標 RDS 建 `erp_metadata` 實體表後,快照內省把系統 schema 當業務分類收進。單版本單條暫不成案;若未來新增系統物件(新 metadata 表 / view schema)再次汙染既有視圖,建議落 `04-databases/01-identifiers.md` 補「系統保留 schema 命名清單 + 內省排除同步」約定(AD-129 的 `_view`/`_en` 後綴保留字亦屬此家族)。

## 已巡視之 pattern 判準(證明跑過)

- 同規則 ≥3 次違反(規範參照分組):v1.5.1 4 條參照分散(introspect 排除 / run 生命週期 / 04-databases 必備欄位 / DDL 併發),無單一規則 ≥3 → 除候選 2(工具盲區例外成案)外無強化候選。
- 同類根因跨 ≥2 版本:並行 / 背景狀態家族(v1.5.0×2 + v1.5.1×2)→ 候選 1;拆解紀律(第 4 版)→ 併入歷史候選佐證,不重列。
- 規範矛盾 / 被推翻:version-bump 裁定 → 候選 3。
- 規則 ≥6 個月未違反(棄用):專案 2026-06 啟動未滿 6 個月,不適用,跳過。
- 已決議候選重列檢查:歷史 16 條候選全數仍為待決議(無 ✅/❌),依規不重列、僅補佐證。

---

> 本次:候選 3(新增 1 / 強化 1 / 修正 1)+ 既有候選佐證 3 組 + 觀察名單 2 條。等 user 決議:✅ 採納開 task(C 段)/ ❌ 拒絕記原因 / 🕐 暫緩下次重評。**提醒:歷史候選已累至 19 條跨 5 份報告,其中「拆解紀律」「共用測試 DB」四度佐證、「RDS 時間型別」已是日常慣例 — 建議近期安排一次集中決議,避免候選繼續積壓。**
