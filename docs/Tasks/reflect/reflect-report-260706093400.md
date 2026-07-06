# reflect-report-260706093400

> **trigger**:version-end(v1.1.0 收口,PR merge 前必觸發)
> **素材**:`docs/Tasks/v1.0.0/fixed.md`(§1–§3)、`docs/Tasks/v1.1.0/fixed.md`(§1–§19,含收口註記)
> **歷史報告**:`docs/Tasks/reflect/` 下無既往 reflect-report(僅 `.gitkeep`),故無已決議候選需排除、無 🕐 暫緩條目需重評
> **性質**:本報告僅為 B 段(反思)候選清單,未動任何 `docs/Design-Base/*`;C 段升級待 user 在 PR 上逐條決議(✅ 採納開 task / ❌ 拒絕記原因 / 🕐 暫緩下次重評)

---

## 摘要

共 **8 個候選**:強化 2 / 新增 3 / 修正 3 / 棄用 0。

| # | 主題 | 類型 | 來源條目數 |
| --- | --- | --- | --- |
| 1 | 拆 task 時「規範連動檔 / 既有結構盤點」納入 affected_files | 強化 | 7 |
| 2 | 共用單元與跨 task 介面契約指派唯一 owner task | 新增 | 6 |
| 3 | 依賴鎖版 / 升版後跑實連煙霧測試 | 新增 | 3 |
| 4 | 規範版本表 / Dockerfile 模板以 Sources of Truth 為準(追認收口變更) | 修正 | 2 |
| 5 | 密碼雜湊規則改「bcrypt 直呼或 argon2」 | 修正 | 1(規範被推翻) |
| 6 | i18n 規範補「單語系內部工具」豁免條款 | 修正 | 1(規範被推翻,涵蓋 3 個前端 task) |
| 7 | 時區規範補 tzdata 鎖版 + DB session timezone 顯式設定驗證 | 強化 | 3 |
| 8 | Acceptance 驗收命令平台中立(Windows locale / tz 資料庫差異) | 新增 | 3(跨 2 版本) |

---

## 候選 1 — 拆 task 時「規範連動檔 / 既有結構盤點」納入 affected_files

- **類型**:強化
- **來源**:fixed.md `v1.1.0 §1`、`v1.1.0 §4`、`v1.1.0 §7`、`v1.1.0 §9`、`v1.1.0 §10`、`v1.1.0 §12`、`v1.1.0 §14`
- **pattern**:v1.1.0 最大宗同型根因(單版 7 條,遠超「同型 ≥ 3」門檻)— orchestrator 拆 task 時 `affected_files` 白名單只列「功能主檔」,規範要求的**連動檔**未列入任何 task,而 worker 依 multi-agent 硬約束不得動白名單外檔案,形成「規範義務與檔案白名單互斥」:新依賴 → `01-versions.md` 套件表(§1);新必填 env → `.env*.example` 全層 + env 登記檔(§4、§12);第三方串接 → `clients/<service>/` 子目錄、`app/schemas/`、`main.py` lifespan(§7);實際鎖定線 → Design-Base 版本表 / Dockerfile 模板(§9);新 route group 頁面 → 被頂替的既有 `page.tsx` 刪除(§10);檔名慣例 → 鎖定框架版本的 deprecation(Next 16 `middleware.ts` → `proxy.ts`,§14)。現行 `02-task-decomposition.md` 只管粒度 / 依賴 / 同檔互鎖,完全沒有「連動檔盤點」步驟 → 規則太弱。
- **建議**:強化 `01-propose/02-task-decomposition.md`,於「拆解原則」後新增「**規範連動檔盤點(硬步驟)**」一節,要求 orchestrator 對每個 task 依其性質跑連動檔 checklist 並列入 `affected_files`(或明確指派給收口 task):
  1. 新增 / 升版依賴 → `docs/Design-Base/00-overview/01-versions.md` 套件表同步(或明列「留收口 task」)
  2. 新增必填 env / secret → `.env.development.example` / `.env.staging.example` / `.env.production.example` 全層 + 前端 `frontend/.env.local.example` / 根 `.env.example` 登記檔
  3. 串第三方 → `app/clients/<service>/` 子目錄四檔 + `app/main.py`(lifespan)+ `app/schemas/`
  4. 新增 route group / 頁面 → 盤點與既有骨架頁面的路由重疊,被頂替頁面的**刪除**也列入 affected_files
  5. 檔名 / 慣例 → 對照鎖定框架版本(`01-versions.md`)的 deprecation / breaking-change 清單,不沿用舊版慣例
  同步在 `01-propose/03-multi-agent-flow.md § 衝突偵測` 補一句:worker 發現規範連動檔不在白名單 → 寫 fixed.md 回報拆解缺口(比照 merge conflict 流程),不得靜默偏離。
- **影響**:不破壞 backward(只約束之後的拆解);v1.1.0 既有偏離已全數於收口處理完畢(§1/§4/§9/§12 收口已補,§7 列下版本候選),無 grandfather 負擔。需改檔:`01-propose/02-task-decomposition.md`(主)、`01-propose/03-multi-agent-flow.md`(回報流程一句)。checklist 同步:`99-code-review/03-pr-self-check.md` 若列有拆解相關檢查項可加一條「連動檔盤點已跑」。
- **driver**:user(df.it.all,規範 owner)review;C 段升級 task 建議由 orchestrator 角色 agent 執行(該檔屬其必讀檔)

---

## 候選 2 — 共用單元與跨 task 介面契約指派唯一 owner task

- **類型**:新增
- **來源**:fixed.md `v1.1.0 §5`、`v1.1.0 §8`、`v1.1.0 §13`、`v1.1.0 §15`、`v1.1.0 §16`、`v1.1.0 §17`
- **pattern**:單版 6 條同型根因,現行拆解方法論**無對應規則** — 「多 task 都需要、但不屬於任一 task 功能主檔」的共用單元 / 跨 task 契約,拆解時無人擁有:後端時間 util `app/utils/datetime.py` 無 owner 暫置 engine.py(§5);雙軌守衛 provider 分流橫跨 task-002/003 無人擁有(§8),連帶前端 silent re-auth 缺 `provider` 欄位(§13);API enqueue ↔ worker `run_etl` 簽章的 run_uid 契約兩 task 各自實作(§15);前端 `ApiEnvelope` / `unwrap` / 錯誤萃取跨 API 檔重複(§16);跨頁共用 UI 單元(Pagination / StatusBadge / datetime 格式化)無 `components/common/` 白名單(§17)。與候選 1 同屬拆解缺口,但機制不同:候選 1 是「規範連動檔漏列」,本候選是「共用資產 / 介面契約無 owner」。
- **建議**:於 `01-propose/02-task-decomposition.md § 拆解原則` 新增兩條:
  1. **共用單元唯一 owner**:規範指定的共用落點(後端 `app/utils/*`、`app/schemas/*`;前端 `types/*`、`utils/*`、`components/common/*`)在拆解時指派唯一 owner task(首個需要者,或獨立基建 task),其 `affected_files` 含該路徑;其他 task 一律 import,禁自寫重複定義
  2. **跨 task 介面契約指定 owner**:跨 task 邊界(API ↔ worker 簽章、共用守衛 / schema 欄位、前後端回應信封)在 task 檔明寫契約內容與 owner task;非 owner task 發現契約不足 → 寫 fixed.md 回報,禁各自演繹
- **影響**:不破壞 backward;v1.1.0 偏離已於收口收斂(§5/§13/§16/§17 收口完成;§8 撤銷註記遷 redis、§15 觸發即得 run_uid 列下版本候選),無需補洞。需改檔:`01-propose/02-task-decomposition.md`。checklist 同步:`99-code-review/03-pr-self-check.md` 可加「共用單元無跨檔重複定義」檢查項(前端已有 `02-frontend/05-components.md § Reuse 規則` 可引用,本候選是把義務前移到拆解期)。
- **driver**:user(df.it.all)review;與候選 1 建議同一個 C 段升級 task 一起改(同檔)

---

## 候選 3 — 依賴鎖版 / 升版後跑實連煙霧測試

- **類型**:新增
- **來源**:fixed.md `v1.1.0 §3`、`v1.1.0 §6`、`v1.1.0 §19`
- **pattern**:單版 3 條同型根因,無對應規則 — 「鎖版組合相容性 bug 只在**實連 / 實跑**路徑爆發,測試替身蓋不到」:passlib 1.7.4 × bcrypt 5.0.0 首次 hash 呼叫即炸(§3);缺 tzdata 使 `ZoneInfo("Asia/Taipei")` 本機直接 raise(§6);redis-py 8 預設 socket_timeout=5s × taskiq-redis BRPOP 使 worker 閒置即無限 reload,InMemoryBroker 測試完全蓋不到(§19)。三者共通:鎖版當下未驗「間接依賴 major 升版」的行為變更,且開發期測試都走替身(CryptContext 未實呼 / Linux 容器有 tzdata / InMemoryBroker)。
- **建議**:兩處落腳:
  1. `00-overview/01-versions.md § 升版流程` 補:「新增 / 升版依賴時,檢查**間接依賴**是否發生 major 升版(lock diff),有則查該套件 changelog 的 breaking-change;鎖版完成後對受影響路徑跑一次**實連煙霧測試**(真 redis / 真 DB / 真雜湊呼叫),不得只以 in-memory 替身驗收」
  2. `03-backend/07-testing.md` 補一節「煙霧測試(實連)」:凡引入 broker / cache / 外部服務 client 的 task,Acceptance 至少含一條實連命令(如 compose 起 redis 後 enqueue 一次、閒置觀察 N 分鐘無異常),與 respx / InMemory 單測並存
- **影響**:不破壞 backward;既有 code 已於收口修復(§3 bcrypt 直呼、§6 tzdata==2026.2、§19 socket_timeout=None + 實連驗證 7 分鐘無 reload),煙霧測試義務只約束之後的依賴變更。需改檔:`00-overview/01-versions.md`、`03-backend/07-testing.md`。checklist 同步:`99-code-review/03-pr-self-check.md` 若含依賴變更檢查項,加「間接依賴 major 升版已查 changelog + 實連煙霧已跑」。
- **driver**:user(df.it.all)review;建議 reviewer 加收口 agent(§19 即收口時實連驗證抓到殘留)

---

## 候選 4 — 規範版本表 / Dockerfile 模板以 Sources of Truth 為準(追認收口變更)

- **類型**:修正
- **來源**:fixed.md `v1.1.0 §1`、`v1.1.0 §9`
- **pattern**:2 條同型「規範內部分歧」— `01-versions.md` 套件表 / `06-Coolify-CD/02-dockerfile-backend.md` 模板硬編版號,與實際 Sources of Truth(`pyproject.toml` / `uv.lock`)分歧時,照規範版本 build 必失敗(§9:python 3.14.0 + uv 0.5.18 讀不了 revision 3 lock),形成「規範表 vs lock 誰是權威」的矛盾。收口(2026-07-06)已直接修改兩檔:補齊套件表、版本同步實際值、加「Sources of Truth 為 pyproject / uv.lock」「image tag 對齊 Sources of Truth」註記 — 此屬 C 段變更先於 reflect 落地,本候選提請 user 在 PR 上**追認**,並補完定位修正。
- **建議**:追認收口對 `00-overview/01-versions.md § Sources of Truth` 與 `06-Coolify-CD/02-dockerfile-backend.md § 規則` 的修改;並於 `01-versions.md § 鎖定原則` 明文定位:「套件表為**快照 / 導覽**,權威為 pyproject / uv.lock(前端為 package.json / lock);兩者分歧時以 SoT 為準並回頭修表」,杜絕下次再以表為準寫 Dockerfile。
- **影響**:不破壞 backward;兩檔收口已改,本候選僅差「快照 vs 權威」一句定位補強。若 ❌ 拒絕追認,需另開 task 回滾收口對該兩檔的修改(不建議 — 回滾後 Dockerfile 與規範再度矛盾)。checklist 同步:無。
- **driver**:user(df.it.all)— 涉及 Design-Base 已被收口修改的既成事實,必須由規範 owner 裁決

---

## 候選 5 — 密碼雜湊規則改「bcrypt 直呼或 argon2」

- **類型**:修正
- **來源**:fixed.md `v1.1.0 §3`
- **pattern**:單條,但屬「規範被推翻」型(fixed-format 明定寫入時機;07-rule-evolution A 段規範被推翻即為升規素材)— `04-databases/03-passwords-and-pii.md` 現行條文「密碼**必** `passlib[bcrypt]` 或 argon2」在鎖定版本組合(passlib 1.7.4 × bcrypt 5.0.0)下不可用:passlib 已停維護(2020 後無 release),其 bcrypt backend 自檢對 bcrypt>=4.1 必炸。production code(`backend/app/core/security.py`)已改 bcrypt 直呼,現行程式碼**持續違反**現行條文 — 規範與現實矛盾,不修則每次 review 都是假警報。
- **建議**:修正 `04-databases/03-passwords-and-pii.md` 首節該條為:「密碼**必** bcrypt(直接呼叫 `bcrypt` 套件,hash 前統一截斷 72 bytes)或 argon2;**禁** passlib 包裝層(已停維護,與 bcrypt>=4.1 不相容)、禁 md5 / sha1 / 明文」;檔頭加變更紀錄(來源 fixed v1.1.0 §3)。連動確認 `03-backend/00-overview.md § 鎖定技術棧` 若列 `passlib[bcrypt]` 一併改為 `bcrypt`(§3 規範參照欄指出該處亦提及)。
- **影響**:不破壞 backward — 既有 code(bcrypt 直呼)修正後即合規,反而消除現存矛盾;`pyproject.toml` 仍留 passlib 依賴的話,可在 C 段 task 順帶評估移除(依賴變更走候選 3 流程)。需改檔:`04-databases/03-passwords-and-pii.md`、`03-backend/00-overview.md`。checklist 同步:`99-code-review/06-security-checklist.md` 若引用 passlib 字樣需同步。
- **driver**:user(df.it.all)review;安全相關,建議 C 段 PR 標注 security 供人工複核截斷 72 bytes 行為

---

## 候選 6 — i18n 規範補「單語系內部工具」豁免條款

- **類型**:修正
- **來源**:fixed.md `v1.1.0 §11`
- **pattern**:單條,但屬「規範被推翻 + 與硬約束矛盾」型,且實際涵蓋 task-009 / 010 / 011 三個前端 task(§11 後續明示「010/011 沿用同做法保持一致」,§16/§17 的前端落檔即為沿用結果)— `02-frontend/00-overview.md § i18n(永遠遵守)`「UI 文字一律 i18n key」與現實三重互斥:骨架無 i18n 基建、依賴鎖版禁 worker 增套件、字典檔不在白名單;且本後台為 zh-TW 單語系內部工具,強上 i18n 是預先設計未存在需求(違 CLAUDE.md 簡潔原則)。現行前端全部頁面持續「違反」該條 — 不修則規範永遠是死文字。
- **建議**:修正 `02-frontend/00-overview.md § i18n(永遠遵守)`,補豁免條款:「**豁免**:單語系內部工具(propose 明示不做多語系)可不建 i18n 基建,UI 文字以語系字串常數集中於元件 / 模組頂部 const(禁散落 JSX);未來轉多語系時另開 i18n 基建 task 統一回收字串。多語系產品仍一律 i18n key,缺漏視為 bug」;檔頭加變更紀錄(來源 fixed v1.1.0 §11)。
- **影響**:不破壞 backward — v1.1.0 前端做法(字串常數集中)修正後即合規(§11 修正欄所載即此形);若未來需多語系,豁免條款已內建退場路徑(另開基建 task)。需改檔:`02-frontend/00-overview.md`。checklist 同步:`99-code-review/04-lint-checklist.md` 若有 i18n 檢查項需標注豁免情境。
- **driver**:user(df.it.all)— 涉及「永遠遵守」層級條款鬆綁,必須規範 owner 裁決

---

## 候選 7 — 時區規範補 tzdata 鎖版 + DB session timezone 顯式設定驗證

- **類型**:強化
- **來源**:fixed.md `v1.1.0 §5`、`v1.1.0 §6`、`v1.1.0 §18`
- **pattern**:同規則(`00-overview/05-timezone.md`)單版 3 次違反 / 落空,達「≥ 3 次 → 規則太弱」門檻 — §5:時間 util 未落規範指定的 `app/utils/datetime.py`(owner 面已由候選 2 涵蓋);§6:規範範式 `ZoneInfo("Asia/Taipei")` 在無 tzdata 環境直接 raise,規範沒說 tzdata 是必備依賴;§18:規範要求 DB session timezone 對齊 Asia/Taipei,但只設 container `TZ` 不會影響 postgres session,`server_default=func.now()` 寫 UTC 與 Python `now_tw()`(+8)混用,前端顯示差 8 小時 — 規範寫了「要一致」但沒給可機械驗證的設定點與驗法,弱到三個 task 都沒守住。
- **建議**:強化 `00-overview/05-timezone.md` 兩節:
  1. `§ 後端 datetime 實踐` 補:「使用 `ZoneInfo` 必在 pyproject 鎖 `tzdata`(跨平台必備;Windows 本機無系統 IANA 資料庫),並允許 `timezone(timedelta(hours=8))` fallback 作防禦」
  2. `§ 資料庫` 補:「DB session timezone 必**顯式**設定於 engine `connect_args={"server_settings": {"timezone": "Asia/Taipei"}}`(容器 `TZ` 不影響 postgres session);驗證方式:同一請求內比對 `server_default` 欄位(如 created_at)與 Python 寫入欄位(如 started_at)為同刻,差 8 小時即未生效」
  另 `04-databases/06-timezone.md`(同主題子檔)同步引用上述設定點。
- **影響**:不破壞 backward — 收口已全數落地(§6 tzdata==2026.2、§18 connect_args 方案並實測同刻),本候選是把收口採用的解法回寫為規範,使下個專案 / 下版本不再踩;API 序列化補 `+08:00` offset 屬 §18 收口遺留的下版本候選,不在本條範圍。需改檔:`00-overview/05-timezone.md`、`04-databases/06-timezone.md`。checklist 同步:`99-code-review/03-pr-self-check.md` 可加「server_default 與 Python 寫入時戳同刻驗證」一項(可機械驗證)。
- **driver**:user(df.it.all)review;建議由後端 area 熟悉者(收口 agent)起 C 段 task,解法即收口實作

---

## 候選 8 — Acceptance 驗收命令平台中立(Windows locale / tz 資料庫差異)

- **類型**:新增
- **來源**:fixed.md `v1.0.0 §1`、`v1.0.0 §2`、`v1.1.0 §6`
- **pattern**:同類根因**跨 2 版本共 3 條**,無對應規則 — 「本機 Windows 與 Linux 容器的平台差異未被 Acceptance / 鎖版考量」:v1.0.0 §1 / §2 皆為 Acceptance 用裸 `open()`(不帶 encoding)在 Windows cp950 locale 下對含繁中的 UTF-8 yaml 必 `UnicodeDecodeError`(兩條同根因,一條被迫把 yaml 註解改 ASCII 犧牲繁中規則);v1.1.0 §6 為 Windows 無系統 IANA tz 資料庫使規範範式實跑即 raise(Linux 容器有 tzdata 所以開發期未被發現)。三條共通:規範 / Acceptance 隱含假設 Linux + UTF-8 環境,本機 dev(Windows)一跑就破。
- **建議**:於 `01-propose/02-task-decomposition.md § Acceptance 寫法` 新增「**平台中立**」規則:「Acceptance 命令不得依賴系統 locale / 系統 tz 資料庫:讀檔一律顯式 `encoding='utf-8'`(或命令前綴 `PYTHONUTF8=1`);時區一律經鎖版 `tzdata`(見 `00-overview/05-timezone.md`);驗收命令須在 Windows 本機與 Linux 容器皆可過」。tzdata 鎖版義務本體落候選 7,本條管 Acceptance 寫法面。
- **影響**:不破壞 backward — v1.0.0 的 ASCII 註解取捨(§1)可依其後續欄還原(Acceptance 改 `encoding='utf-8'` 後 yaml 註解可回繁中),是否還原由 user 決定(grandfather:不強制回改);v1.1.0 §6 已由 tzdata 鎖版解決。需改檔:`01-propose/02-task-decomposition.md`(與候選 1 / 2 同檔,建議同一 C 段 task 處理)。checklist 同步:無。
- **driver**:user(df.it.all)review;與候選 1 / 2 併同一升級 task(同檔,避免三次 PR 改同節)

---

## 已巡視、未成案素材(寧空勿湊聲明)

四條 pattern 判準均已套用;下列條目經評估**不**立候選:

- `v1.1.0 §2`(etl schema 多來源表達力):設計取捨非規範問題,後續是產品 backlog(下版本增 `etl_mappings.source_table` 欄位),不屬 Design-Base 升規範疇
- `v1.0.0 §3`(AWS/RDS Acceptance 待人工):執行環境邊界個案,無同型累積
- **棄用候選 = 0**:專案 fixed 素材始於 2026 年內(v1.0.0 條目無時間欄、v1.1.0 全數 2026-07),不存在「≥ 6 個月未違反」的可判定窗口;下次 reflect(累積更長歷史後)再評
- **修正判準(規範矛盾)**:除已立案之候選 4 / 5 / 6 外,未發現其他跨檔規則衝突
