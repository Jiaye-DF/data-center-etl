# fixed.md — v1.4.1

## §1 — `users.role_pid` 暫不收 NOT NULL(偏離 task-001 規格文字)

- **時間**:2026-07-10T00:00+08:00
- **commit / PR**:(見本次 task-001 commit)
- **影響檔案**:`backend/app/models/user.py`、`backend/alembic/versions/v7_add_v141_roles.py`
- **問題**:task-001 規格文字要求 migration 最終「收 NOT NULL」;若照字面實作(`role_pid` 欄位
  DB 端 NOT NULL、SQLAlchemy model 端 `nullable=False`),會讓 `UserRepository.create()`
  (建立使用者的唯一入口,`backend/app/repositories/user_repo.py`)在 task-002 補寫入
  `role_pid` 之前,任何新建使用者(本地帳密註冊、`ensure_init_admin` 初始管理員、
  SSO 首次登入自動建 viewer)一律因違反 NOT NULL 而失敗;且 `user_repo.py` **不在**
  task-001 的 `affected_files` 白名單內,不可在本 task 一併修正。
  更嚴重的是:既有多支測試檔(`test_auth.py`/`test_sso.py`/`test_audit_log.py`/
  `test_runs_api.py`/`test_schedule_api_v131.py`/`test_snapshot_service.py`/
  `test_sync_api.py`)皆以 `Base.metadata.create_all` 建 schema(非跑 migration),
  這些檔案共用的 `role_pid` 欄位定義若在 SQLAlchemy model 端就是 NOT NULL 且無
  可用 default,會讓上述**既有測試全數回歸失敗**(違反本 task Acceptance「pytest
  全綠(既有測試不迴歸)」)。
- **根因**:task 拆解時,「roles 表地基」(001)與「授權鏈路寫入路徑改接 role_pid」(002)
  被拆成兩個序列 task,但兩者對 `role_pid` NOT NULL 約束的隱含相依未被察覺 ——
  NOT NULL 約束的前提(所有寫入路徑都會填值)要到 002 才成立,001 卻要求提前收
  NOT NULL,造成「規格內部時序矛盾」(地基 task 不能獨立滿足自己訂的驗收條件)。
- **修正**:`role_pid` 保留 `nullable=True`(DB 與 SQLAlchemy model 皆然),不加
  NOT NULL 約束;既有(migration 前)使用者列仍 100% backfill(count(NULL)=0,
  以 Acceptance 逐條驗證通過),僅新建使用者路徑在 002 落地前可能產生 `role_pid
  IS NULL` 的列(對外行為不受影響,`role` 字串欄位仍是實際授權判斷依據,
  002 才切換讀取來源)。
- **規範參照**:`docs/Design-Base/04-databases/08-alembic.md`(migration 冪等 / 安全);
  task-001 規格本身(`docs/Tasks/v1.4.1/tasks/task-001-roles-table-and-backfill.md`
  §「migration」第 5 步「收 NOT NULL」)
- **後續**:task-002 落地(`user_repo.create()` 改寫入 `role_pid`)後,建議**另開一個
  後續 migration**(非改動本次 v7)幫 `role_pid` 收 NOT NULL,並同步將
  `backend/app/models/user.py` 的 `role_pid` 改回 `nullable=False`;reflect 候選 ——
  「單一 migration 完成 backfill」的拆解原則與「跨 task 序列相依的寫入路徑」相衝突時,
  應如何在 propose-to-tasks 階段就攔下(例如 001 的 Acceptance 不該早於寫入路徑落地
  就要求收緊約束)。

## §2 — 持久複用的共用測試 DB(`data_center_etl_test`)schema drift

- **時間**:2026-07-10T00:00+08:00
- **commit / PR**:(見本次 task-001 commit;本條修正**未**進 commit,純本機環境修復)
- **影響檔案**:無程式碼異動(本機 `data_center_etl_test` / `data_center_etl_v141_test`
  兩個測試 DB 的實體 schema);相關既有測試檔:`test_auth.py`、`test_audit_log.py`、
  `test_runs_api.py`、`test_schedule_api_v131.py`、`test_snapshot_service.py`、
  `test_sync_api.py`、`test_sso.py`、`test_mirror_sync_incremental.py`、
  `test_rds_table_meta_repo_v130.py`、`test_schedule_repo_v131.py`、
  `test_snapshot_autoschedule_v131.py`(共用 `TEST_DB_NAME = "data_center_etl_test"`)
- **問題**:`uv run pytest` 全量跑時,`test_auth.py` / `test_audit_log.py` 多支測試因
  `sqlalchemy.exc.ProgrammingError: column users.role_pid does not exist` 失敗。
- **根因**:上述測試檔的 `_prepare_test_db` fixture 一律用
  `await conn.run_sync(Base.metadata.create_all)` 建 schema,而 `create_all` **不會**
  為已存在的表補新欄位(只在表不存在時才 CREATE TABLE)。本機的
  `data_center_etl_test` 資料庫在 task-001 之前的多次測試執行中已建過 `users` 表
  (無 `role_pid` 欄),task-001 幫 `User` model 加了 `role_pid` 欄位後,這些檔案
  的 `create_all` 對既有 `users` 表是 no-op,實體 schema 未跟上 model 定義,
  於是任何 `select(User)`(因 `role_pid` 現為 mapped column,一律被選取)當場
  炸 `UndefinedColumnError`。真正全新環境(如 CI 的 ephemeral DB)不會踩到 ——
  第一支跑的測試檔 `create_all` 建表時就會用最新 metadata 建出正確 schema。
  這屬本機 dev 環境長期複用測試 DB 的已知風險,`test_schedule_repo_v131.py` /
  `test_seed_etl_config.py` 過去已用「補充 `ALTER TABLE ... ADD COLUMN IF NOT
  EXISTS`」的手法在**自己專屬**的測試 DB 上處理過同類問題,但共用
  `data_center_etl_test` 的多支測試檔彼此都未做這件事,沒有單一檔案「擁有」
  該 DB、也沒人負責在 schema 演進時補丁。
- **修正**:對本機 `data_center_etl_test` 執行一次性、純新增的
  `ALTER TABLE users ADD COLUMN IF NOT EXISTS role_pid BIGINT` +
  `CREATE INDEX IF NOT EXISTS idx_users_role_pid ON users (role_pid)`
  (無 DROP,符合 CLAUDE.md 底線),使其等效於「全新環境跑一次 create_all」的
  結果;修正後 `uv run pytest`(227 個測試)全綠,重跑兩輪穩定。此修正僅止於
  本機測試 DB 的實體 schema,**不**改動任何程式碼或既有測試檔(不在 task-001
  白名單)。
- **規範參照**:`docs/Design-Base/03-backend/07-testing.md`(真 DB 測試慣例)
- **後續**:reflect 候選 —「共用持久測試 DB(`data_center_etl_test`)在 model 加欄後
  無人補丁」是系統性缺口,可能隨每個新增欄位的 task 重演;建議評估
  (a) 共用測試 DB 改為每次 session 開頭一律 `ALTER ... ADD COLUMN IF NOT EXISTS`
  跑一輪「schema sync」共用 fixture,或 (b) 改各測試檔各自使用獨立 DB 名
  (犧牲一些建表時間換取隔離),或 (c) CI 固定用全新 DB(若尚未如此)、
  僅本機 dev 需要此類補丁,風險可接受但應在 `07-testing.md` 補一句提醒。

## §3 — v8 收 NOT NULL 與 task-001 產物測試硬衝突,`test_models_v141.py` 白名單外最小修正

- **時間**:2026-07-10T00:00+08:00
- **commit / PR**:(見本次 task-002 commit)
- **影響檔案**:`backend/tests/test_models_v141.py`(**不在** task-002 `affected_files`
  白名單內)、`backend/alembic/versions/v8_enforce_users_role_pid_not_null.py`
- **問題**:task-002 規格新增的 v8 migration(`role_pid` 收 NOT NULL)與 task-001
  產出的 `test_models_v141.py` 兩處硬衝突:(1) 該檔 session fixture 對實跑 migration
  的獨立測試 DB 插入「無 `role_pid` 的舊 schema user」— v8 套用後(downgrade 為
  no-op,NOT NULL 不會鬆回)在**全新環境**首輪 upgrade head 即收約束,該 INSERT
  必炸;(2) `test_new_user_without_role_pid_still_insertable` 明文驗證「無 role_pid
  仍可插入」的過渡態,v8 落地後該過渡態被依規格終結,測試必紅,直接違反本 task
  Acceptance「pytest 全綠」。但該檔不在 task-002 白名單。
- **根因**:task-002 規格中途補入「v8 收 NOT NULL」段(承接 §1 後續)時,
  `affected_files` 白名單未同步盤點「哪些既有測試固定了即將被終結的過渡態行為」——
  白名單與規格演進脫鉤,和 §1 同屬「跨 task 相依未在拆解層被察覺」的變體。
- **修正**:對 `test_models_v141.py` 做最小必要修正(僅動硬衝突處,不重構):
  (1) fixture 的 legacy user INSERT 改以子查詢帶入 `role_pid`(v7 backfill 斷言退化為
  「關聯對應正確」驗證;v7 對 NULL 列的 backfill 已在 task-001 驗證過,
  v8 之後依設計無法再重現);(2) 原過渡態測試改寫為
  `test_role_pid_not_null_enforced_after_v8`(驗 `information_schema` is_nullable='NO'
  + 無關聯插入拋 IntegrityError);(3) `test_user_role_pid_fk_and_index` 的過時註解
  同步更新。model 端 `role_pid` 仍為 `nullable=True`(`models/user.py` 亦不在白名單,
  且改動會連動更多既有斷言)→ DB 端已 NOT NULL、model 端未收緊的不一致留待後續。
- **規範參照**:`docs/Tasks/v1.4.1/tasks/task-002-auth-chain-role-source.md`
  §「規格」收 NOT NULL 段;`01-propose/03-multi-agent-flow.md`(白名單協議)
- **後續**:(a) task-003 或收口時將 `models/user.py` 的 `role_pid` 收為
  `Mapped[int]` / `nullable=False`,並同步修 `test_user_role_pid_fk_and_index`;
  (b) reflect 候選 — 規格中途補段(尤其終結某過渡態的 migration)時,
  `affected_files` 應同步重盤「固定該過渡態的測試」。

## §4 — `UserRepository.create` 依賴 roles seed:共用測試 DB 在全新環境的隱性前提

- **時間**:2026-07-10T00:00+08:00
- **commit / PR**:(見本次 task-002 commit)
- **影響檔案**:無程式碼異動(純風險記錄);相關:`backend/tests/test_audit_log.py`、
  `test_runs_api.py`、`test_schedule_api_v131.py`、`test_snapshot_service.py`、
  `test_sync_api.py`(皆直呼 `UserRepository.create`,且皆不在 task-002 白名單)
- **問題**:task-002 起 `UserRepository.create` 依 `roles.code` 查表建關聯、
  查無即 fail-fast(規格紅線)。上述非白名單測試檔共用 `data_center_etl_test`
  且以 `create_all` 建 schema(只建表、不 seed);**全新環境**首次跑
  `uv run pytest` 時按字母序 `test_audit_log.py` 先於 `test_auth.py` 執行,
  彼時 roles 表為空,所有建立使用者的測試將集體 fail-fast。
- **根因**:與 §2 同源 —「create_all 建 schema 的測試 DB」與「migration 才會 seed
  的資料前提」之間無人負責;本 task 只能在白名單內的 `test_auth.py` /
  `test_sso.py` fixture 補冪等 seed,無法覆蓋其他檔。
- **修正**:本機 `data_center_etl_test` 的 roles 已存在 admin / viewer(先前已
  seed 過),本機全量 pytest 231 全綠,**無**環境異動;`test_auth.py` /
  `test_sso.py` 的 session fixture 已補冪等 seed(對齊 v7 的固定 uid),
  該兩檔單獨在全新 DB 跑亦可自立。
- **規範參照**:`docs/Design-Base/03-backend/07-testing.md`(真 DB 測試慣例)
- **後續**:併入 §2 的 reflect 候選一起決議 — 若採「session 開頭 schema sync 共用
  fixture」方案,應同時涵蓋「內建 seed 資料 sync」(roles 這類 migration-seeded
  的地基資料);在那之前,全新機器首次跑全量 pytest 前需先確保共用測試 DB
  已有 roles seed(跑一次 `test_auth.py` 或手動 INSERT 皆可)。

## §5 — `models/user.py` 收 NOT NULL 依 §3 預告連動 `test_models_v141.py`,白名單外最小修正

- **時間**:2026-07-10T00:00+08:00
- **commit / PR**:(見本次 task-003 commit)
- **影響檔案**:`backend/tests/test_models_v141.py`(**不在** task-003 `affected_files`
  白名單內;`backend/app/models/user.py` 在白名單內)
- **問題**:task-003 規格明確要求「`models/user.py` 的 `role_pid` mapped_column 收緊
  `nullable=False`」(DB 端已由 v8 收 NOT NULL,model 端補齊),但 task-001 產出的
  `test_models_v141.py::test_user_role_pid_fk_and_index` 明文斷言
  `columns["role_pid"].nullable is True`(當時刻意驗證「model 端暫留 nullable=True」
  的過渡態,見 fixed.md §3)。model 端收緊後該斷言與新狀態直接矛盾,`uv run pytest`
  全量跑必紅,違反 Acceptance「全套不迴歸」。但該檔不在 task-003 白名單。
- **根因**:與 §3 同源 —§3 的「後續」欄位當時已明確預告「task-003 或收口時將
  `models/user.py` 的 `role_pid` 收為 `nullable=False`,並同步修
  `test_user_role_pid_fk_and_index`」,但 task-003 規格 / 白名單撰寫時未回頭核對
  §3 的這條待辦,`affected_files` 未納入該測試檔,規格文字與白名單再度脫鉤
  (第三次同型態問題,見 §3「後續」reflect 候選)。
- **修正**:僅改動衝突的單一斷言行(`nullable is True` → `nullable is False`)+
  對應行內註解更新,不動其餘斷言 / fixture / 其他測試邏輯。修正後
  `test_models_v141.py` 9 個測試全綠,`uv run pytest` 全量 239 個測試全綠,
  `uv run mypy .` 維持 42 個既有錯誤(無新增,含本檔既有的 3 個 `FromClause` 型別
  已知錯誤,行號隨編輯位移但錯誤數不變)。
- **規範參照**:`docs/Tasks/v1.4.1/tasks/task-003-roles-users-admin-api.md`
  §「規格」「承接 task-002 尾巴」段;`docs/Tasks/v1.4.1/fixed.md` §3「後續」;
  `01-propose/03-multi-agent-flow.md`(白名單協議)
- **後續**:reflect 候選(併入 §3 同型態候選)——「fixed.md 條目自身的『後續』
  待辦,在下一個 task 規格撰寫階段應被系統性核對並反映到白名單」,否則會重複
  在每個接手 task 上演「白名單外最小修正 + 補一條 fixed.md」。

## §6 — task-003 Acceptance 的 curl/jq 驗證指令與 ApiResponse 殼規範衝突,採規範優先

- **時間**:2026-07-10T00:00+08:00
- **commit / PR**:(見本次 task-003 commit)
- **影響檔案**:無程式碼異動(純驗證方式偏離記錄);相關:
  `backend/app/schemas/role.py`(`RoleListResponse.items`)
- **問題**:task-003 Acceptance 逐字寫
  `curl ... | jq -e '[.data[].code] | sort == ["admin","viewer"]'`,語法上假設
  `GET /api/v1/roles` 的 `ApiResponse.data` 直接是陣列。但
  `docs/Design-Base/03-backend/01-routing.md`「統一回應外殼」明文:「`data`:
  `null` 或 dict;**禁**直接為 array(列表須 `{items: [...], total}`)」——本 task
  規格本文「`GET /api/v1/roles`」條目亦要求回「角色列表」,實作依此規範以
  `RoleListResponse{items: [...]}` 包裝,`data` 為 dict 非 array,故字面
  `jq '[.data[].code]'` 語法在本機驗證會回空陣列(非炸錯,但比對必為 false)。
- **根因**:Acceptance 驗證指令撰寫時未同步核對同一份 task 檔規格段落與
  binding 的 01-routing.md 外殼慣例,兩處出現「陣列殼 vs dict-items 殼」的
  字面不一致;`03-multi-agent-flow.md` 白名單協議管的是「改哪些檔案」,未涵蓋
  「Acceptance 驗證指令本身的正確性」,此類落差目前無自動核對機制。
- **修正**:不改規範(01-routing.md 優先於本 task 檔字面,依
  CLAUDE.md「規範優先順序」);以等價語意驗證取代逐字指令 ——
  `curl -s -b <admin cookie> http://localhost:8000/api/v1/roles` 後以
  `jq -e '[.data.items[].code] | sort == ["admin","viewer"]'`(或本機無 jq 時以
  python 等價解析)驗證,本機對 dockerized 服務(`docker compose up -d --build`
  後)實測通過(`codes: ['admin', 'viewer']` → PASS)。
- **規範參照**:`docs/Design-Base/03-backend/01-routing.md`「統一回應外殼」;
  CLAUDE.md「規範優先順序」(`docs/Design-Base/*` > 本檔案 > `docs/Tasks/*`)
- **後續**:reflect 候選 —「propose-to-tasks 產出的 Acceptance 驗證指令,若涉及
  API 回應結構(如 jq path),應在拆解階段對照 01-routing.md 等 binding
  規範跑一次一致性檢查,避免字面指令與規範不符导致驗證卡關」。
