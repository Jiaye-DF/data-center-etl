# reflect-report-260709132015

> **trigger**:version-end(v1.4.0 六 task 完成,PR merge 前)
> **素材**:`docs/Tasks/v1.0.0/fixed.md`(§1–§3)、`v1.1.0/fixed.md`(§1–§19)、`v1.4.0/fixed.md`(§1–§5;§3–§5 為本次收口依 04-fixed-format 補記之 A 段條目 — 素材來源為 worker 完成回報與 propose § 風險 / tasks-v1.4.0.md § 拆解摘要既有註記,非事後杜撰)
> **歷史報告**:`reflect-report-260706093400.md`(8 候選)— **全數尚未決議**(無 ✅/❌/🕐 記錄),依規則不重列、不重評;本報告僅收 v1.4.0 新素材。與前次候選同檔落腳者於「影響」欄註明合併建議。
> **性質**:僅 B 段反思,未動任何 `docs/Design-Base/*`;C 段升級待 user 逐條決議(✅ 開 task / ❌ 記原因 / 🕐 暫緩)。

---

## 摘要

共 **4 個候選**:強化 1 / 新增 2 / 修正 1 / 棄用 0。

| # | 主題 | 類型 | 來源 |
| --- | --- | --- | --- |
| 1 | multi-agent 共用工作樹 git 紀律(禁全域 stash/checkout/reset)+ worktree 隔離指引 | 新增 | v1.4.0 §3 |
| 2 | 並行 worker 測試 DB 使用約定 | 新增 | v1.4.0 §5 |
| 3 | 版本 bump 規則補「內部後台權限收緊」例外條款 | 修正 | v1.4.0 §4 |
| 4 | SQL 安全規則補「成品 DDL 禁二次 `text()` 解析,必走 `exec_driver_sql`」 | 強化 | v1.4.0 §1 |

---

## 候選 1 — multi-agent 共用工作樹 git 紀律 + worktree 隔離指引

- **類型**:新增
- **來源**:fixed.md `v1.4.0 §3`
- **pattern**:單版單條,但屬「協議層系統性缺口」而非個別失誤 — `03-multi-agent-flow.md` 的互鎖協議只鎖「檔案白名單不重疊」,對**影響全工作樹的 git 操作**(stash / checkout -- . / reset)完全無約束;只要 ≥ 2 worker 共用一份 working directory,任一 worker 出於正當動機(§3 即為建 mypy 乾淨基線)跑一次全域操作,就會清掉所有他人未提交工作。此為協議設計必然踩到的洞(白名單互鎖在 git 全域操作面前失效),非「某 worker 忘了」;v1.4.0 實戰已造成 task-003 全部 WIP 被清、整包重做。
- **建議**:於 `01-propose/03-multi-agent-flow.md § 衝突偵測` 後新增「**工作樹紀律**」一節:
  1. 共用工作樹期間,worker **禁**執行影響 affected_files 白名單以外檔案的 git 操作:`git stash`(任何形式)、`git checkout/restore` 整樹或他人檔案、`git reset`、`git clean`;需要乾淨基線比對 → 用 `git stash push -- <own files>`(限定 pathspec)或 `git diff HEAD -- <own files>` 唯讀比對替代
  2. commit 權責明定:由 orchestrator 統一以 pathspec 分批 commit(每 task 完成即刻提交保護),或 worker 僅 `git add <own files>` + commit(禁 `git add -A`);二擇一於派工時宣告
  3. 隔離升級路徑:並行 worker ≥ 3 或任務需頻繁 git 基線操作時,orchestrator 應改用 git worktree per-worker 隔離,收口時由 orchestrator 合併
- **影響**:不破壞 backward(純流程規範,不涉程式碼);既有事故已閉環(v1.4.0 §3:重做 + 即刻 commit 策略,遺留 stash@{0} 待 user drop)。需改檔:`01-propose/03-multi-agent-flow.md`(主)。與前次候選 1(同檔補「連動檔盤點回報」一句)落腳相同,建議 C 段同一 task 處理。checklist 同步:無(流程面,無機械驗證點)。
- **driver**:user(df.it.all,規範 owner)review;C 段建議由 orchestrator 角色 agent 執行(該檔屬其必讀檔,且事故第一手在其 session)

---

## 候選 2 — 並行 worker 測試 DB 使用約定

- **類型**:新增
- **來源**:fixed.md `v1.4.0 §5`
- **pattern**:單版單條,但屬「規範缺口 × multi-agent 拆解方法論」交叉的系統性問題 — `03-backend/07-testing.md` 過薄(前次 scan 報告第 7 章第 4 點、本次 scan 報告第 7 章第 2 點連續兩次點名),完全未定義測試 DB 生命週期與並行使用;測試檔以固定 DB 名 + 清表 fixture 設計天然假設單執行者,而 multi-agent 拆解(`02-task-decomposition.md`)鼓勵後端 task 並行、每個 task 的 Acceptance 又都含 `uv run pytest` 全套 — 兩規範疊加**必然**在波次內互踩。v1.4.0 實戰:task-001 / task-003 併跑產生 FK 違反 / unique 衝突 / 認證失敗等間歇錯誤且集合每次不同,致 task-001 無法在任務內完成「全套全綠」驗收,靠 orchestrator 收口獨占補跑繞開。
- **建議**:於 `03-backend/07-testing.md` 新增「**並行執行約定**」一節(二擇一,拆解期宣告):
  1. **獨立 DB 方案**:測試 DB 名走 env(如 `TEST_DATABASE_NAME`,預設 `data_center_etl_test`),multi-agent 派工時每 worker 指派後綴(`_w1`/`_w2`),conftest 依 env 建庫 — 各 worker 全程可跑全套
  2. **序列化方案**(最小成本):明定「單檔測試(`pytest tests/test_x.py`)worker 可隨時跑;**全套** `uv run pytest` 屬收口獨占動作,由 orchestrator 在無其他 worker 活動時執行」,並要求拆 task 時把「全套全綠」從各 task Acceptance 移到收口 gate
  同步在 `01-propose/02-task-decomposition.md § Acceptance 寫法` 補一句:「多 worker 並行版本,共用資源類驗收(全套測試 / docker build)標註『收口獨占』,不列入單 task 阻斷項」。
- **影響**:不破壞 backward;既有測試檔在方案 2 下零改動(v1.4.0 實際採用的即方案 2 的臨場版),方案 1 需動 conftest/env(一次性小改)。需改檔:`03-backend/07-testing.md`(主)、`01-propose/02-task-decomposition.md`(一句)— 後者與前次候選 1/2/8 同檔,建議 C 段併同一 task。checklist 同步:`99-code-review/03-pr-self-check.md` 若列「全套測試綠」項,標註執行時機為收口。
- **driver**:user(df.it.all)review;07-testing.md 擴充可與前次 scan 既點名的「測試 DB 生命週期」缺口一併補(同檔同段)

---

## 候選 3 — 版本 bump 規則補「內部後台權限收緊」例外條款

- **類型**:修正
- **來源**:fixed.md `v1.4.0 §4`(propose-v1.4.0.md § 風險 2026-07-09 user 裁定;tasks-v1.4.0.md § 拆解摘要明文提醒走 reflect)
- **pattern**:「規範被推翻」型(07-rule-evolution A 段明定為升規素材)— `05-version-bump.md`「權限收緊,既有 user 失去存取 → bump major」在內部後台情境被 user 裁定推翻:受影響者(member/viewer)即權限收緊的**目標對象**而非契約受害者,一刀切 major 的溝通成本大於語意效益。不修則同型裁定每次都要重新走「規範衝突 → user 裁決」流程,且規範與既成版號(v1.4.0)永久矛盾。
- **建議**:修正 `01-propose/05-version-bump.md § breaking 判準` 權限收緊條,補例外:「**例外**:公司內部後台(非對外產品/API 契約)之權限收緊,若受影響角色即本次收緊的目標對象(如全面 admin-only),經 propose § 風險載明 user 裁定後可走 **minor**;CHANGELOG 必標示權限變更並列受影響角色。對外產品 / 有第三方依賴之 API 權限收緊仍一律 major」;檔頭加變更紀錄(來源 fixed v1.4.0 §4)。
- **影響**:不破壞 backward — v1.4.0 版號為既成事實,例外條款使其由「被推翻」轉為「合規」;未來同型情境有明確路徑(propose 載明 + CHANGELOG 標示)而非逐次裁決。需改檔:`01-propose/05-version-bump.md`。checklist 同步:`06-changelog.md` 若有格式表,確認「權限變更」標示慣例一致。
- **driver**:user(df.it.all)— 涉及版號治理判準鬆綁,必須規範 owner 裁決(且裁定本人即 user,追認性質)

---

## 候選 4 — SQL 安全規則補「成品 DDL 禁二次 `text()` 解析,必走 `exec_driver_sql`」

- **類型**:強化
- **來源**:fixed.md `v1.4.0 §1`
- **pattern**:單條 fixed,但同一根因**埋於兩處、跨兩個版本**(v1.1.0 `writer.write_table` 首埋 → v1.2.0 `mirror.write_mirror` 沿用同寫法)且屬「規則盲區」— `04-databases/04-sql-safety.md` 管到「識別字白名單 + `quote_literal` 跳脫組裝」為止,未規範**組裝完成後的執行方式**;兩處都把已跳脫的成品 DDL 再包 `text()`,而 `text()` 會把字串中 `:緊接文字`(如 COMMENT 內容 `('Y':是)`)誤判為 bind 參數 → runtime raise。潛伏近三個版本直到 DS 字典出現冒號描述才爆,同步整表失敗。規則覆蓋終點太早 = 太弱,符合強化判準。
- **建議**:強化 `04-databases/04-sql-safety.md § DDL 組裝`(或對應段落)補一條:「白名單 + `quote_literal` 組裝完成的 DDL 字串已是**成品**,執行**必**走 `conn.exec_driver_sql(stmt)` 直送 driver;**禁**再包 `sqlalchemy.text(stmt)`(`text()` 會把字面值中的 `:xxx` 誤判為 bind 參數;成品 DDL 無 bind 需求)。需要 bind 參數的語句反之必走 `text().bindparams()`,兩者不得混用」;附 v1.4.0 §1 案例一行(COMMENT 含 `('Y':是)` 觸發)作為 rationale。
- **影響**:不破壞 backward — 兩處呼叫點已於 v1.4.0 §1 修正(`exec_driver_sql` + 回歸測試釘住),既有 code 合規;新規則只防未來新增 DDL 路徑重蹈。需改檔:`04-databases/04-sql-safety.md`。checklist 同步:`99-code-review/` 若有 SQL 安全檢查項,加「成品 DDL 走 exec_driver_sql」一條(可 grep `text(` × `COMMENT ON|CREATE|ALTER` 機械掃)。
- **driver**:user(df.it.all)review;C 段可由後端 area agent 執行,解法即 v1.4.0 §1 已驗證實作

---

## 已巡視、未成案素材(寧空勿湊聲明)

四條 pattern 判準均已套用於 v1.0.0 §1–§3、v1.1.0 §1–§19、v1.4.0 §1–§5 全量素材;下列不立候選:

- `v1.4.0 §2`(StatusBadge 折行):單一 CSS 缺漏,個別失誤層級,無同型累積、無規則可落(`06-rwd.md` 已有 RWD 地板,此屬實作疏漏非規則太弱)→ 去噪
- **同規則 ≥ 3 次違反(強化判準)**:v1.4.0 素材中無任一規則達 3 次;候選 4 以「同根因跨版本複製 + 規則覆蓋終點太早」立案,非次數門檻
- **棄用候選 = 0**:fixed 素材時間窗仍不足 6 個月(2026-07 起),無可判定「長期未違反」之規則;下次 reflect 再評
- **規範矛盾(修正判準)**:除候選 3 外,v1.4.0 未新增跨檔規則衝突(scan 報告第 7 章第 1 點 compose vs 01-versions.md 矛盾屬**實作違規**未被推翻 — 修 compose 即解,不需改規則,已列 scan 優先序)
- **前次 8 候選**:全數未決議,依規則不重列;請 user 於 PR 上一併決議兩份報告共 **12 個候選**

---

> 本報告 4 個候選(新增 2 / 修正 1 / 強化 1)。連同前次未決議 8 候選,共 12 條等 user 決議:✅ 採納 → 開 C 段升級 task;❌ 拒絕 → 於報告條目下記原因;🕐 暫緩 → 下次重評。落腳檔重疊建議:候選 1 + 前次候選 1(03-multi-agent-flow.md / 02-task-decomposition.md)、候選 2 + 前次候選 3(07-testing.md)可各併一個 C 段 task。
