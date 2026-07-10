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
