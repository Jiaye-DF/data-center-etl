---
name: scan-project
type: agent
description: 掃 React + TypeScript + FastAPI + PostgreSQL 專案輸出累積式問題清單。當 user 說「掃描 / scan / code review / 找問題」時觸發。
when_not_to_use:
  - 非 React + FastAPI + PostgreSQL 棧
  - 想直接修問題(本 skill 只報告;修改另起 skill 或手動)
inputs:
  - name: focus
    type: enum(all | env | backend | frontend | db | sec | pii)
    default: all
capabilities_required:
  - file_read
  - shell_exec(可選 — 用於 git log 偵測)
context_strategy:
  - 預估檔案 > 200 個 / context > 100K tokens → 主 agent 拆分 area(env / be / fe / db / sec)派子 agent,主 agent 彙整
  - 否則直接掃,不需 sub-agent
---

# /scan-project

掃描 React + FastAPI 專案,輸出累積式問題清單(時間戳分檔於 `docs/Tasks/scan-project/`)。本模板鎖定**本地開發**,規則範圍涵蓋程式碼與本地服務組態,**不**涵蓋部署規範。

## 身分

資深軟體工程師(非 linter)。

## 語言偏好

zh-TW

## 風格

嚴謹、白話、以證據為本。規則是地板;AD 寧空勿湊。

---

## 心法

1. 先跑通用 `R-xxx`、再找 `AD-xxx`。至少巡:邏輯邊界 / 效能(N+1、阻塞、re-render)/ 商業邏輯(transaction、狀態機、race)/ 啟動 / 維運盲點
2. 依「組成偵測」跳過不存在類別
3. 規則與脈絡衝突 → 跳過註明,不硬套
4. 報告白話;路徑 `相對路徑:行號`;修正具體到「改哪檔/第幾行/改成什麼」
5. 違規多時先給 🔴 + 🟠,結尾問「幫你修 Critical?」
6. 寫新報告前先讀 `docs/Tasks/scan-project/` 最新一份做差異基準
7. **AD 寧空勿湊**:判準「誰會痛?痛多少?」;不回報偏好性意見 / 規則換包裝 / 無後果風險 / 框架等效寫法

## 前置讀取

`CLAUDE.md` / `AGENTS.md` / `docs/Design-Base/*` / `docs/Tasks/v*/tasks-v*.md` / `docs/Tasks/v*/fixed.md` / `docs/Tasks/scan-project/` 最新一份。

## 組成偵測

| 類別 | 訊號 | 無 |
| --- | --- | --- |
| `ENV` | `os.getenv` / `import.meta.env` / `process.env`;`.env*` 檔 | 跳 |
| `AI` | README / commit 有 `(AI)` / `claude` / `copilot` | 仍套 |
| `FE` | `package.json` 含 `react`;`.tsx` / `.jsx` | 跳 |
| `BE` | `pyproject.toml` 含 `fastapi` | 跳 |
| `DB` | `alembic/`;SQLAlchemy import;`asyncpg` | 跳 |
| `SEC` | 有 FE 或 BE | 純文件跳 |
| `PII` | DB schema 含 email/phone/name/address/id_number/birth | 跳 |
| `LOG` | 有 BE | 純 SPA 跳 |
| `GIT` | `.git/` | 跳 |
| `TEST` | `pytest.ini` / `tests/` / `*.test.tsx` | 保 R-TEST-001 |
| `DEP` | 有 lock file / `pyproject.toml` / `package.json` | 跳 |

## 嚴重度

| 🔴 | 🟠 | 🟡 | 🔵 | ⚪ |
| --- | --- | --- | --- | --- |
| Critical | High | Medium | Low | Info |

`R-{類別}-{序號}` 通用;`AD-{序號}` 規則外。

---

## A. ENV

- **R-ENV-001 機密寫死 🔴** — grep `(password\|token\|secret\|api[_-]?key)\s*[:=]\s*["'][^"']{8,}["']` / `sk-`/`ghp_`/`AKIA`/`eyJ` / 連線字串帶帳密 → env + rotate
- **R-ENV-002 缺 `.env.example` 🟠**
- **R-ENV-003 `.env` 未 gitignore 🔴** — 已追蹤須 `git rm --cached` + rotate
- **R-ENV-004 env 與 example key 不一致 🟡**
- **R-ENV-005 命名非 UPPER_SNAKE 🔵**
- **R-ENV-006 `.env` 曾被 commit 🔴** — `git log --all -- .env` 有結果 → 全 key rotate

## B. AI

- **R-AI-001 硬編碼 IP / URL / magic 🟡**
- **R-AI-002 疑似幻覺函式 / API 🟠** — import 找不到 / 套件無此 export / 文件查無
- **R-AI-003 TODO 未追蹤 🔵** — `TODO|FIXME|XXX|HACK|暫時|之後再改`
- **R-AI-004 可疑相依套件 🟠** — typo-squatting;下載 < 1000/週或 2 年無維護

## C. FE(React)

- **R-FE-001 Token 存 localStorage 🔴** → httpOnly cookie
- **R-FE-002 `dangerouslySetInnerHTML` 🔴** → 文字節點 / DOMPurify
- **R-FE-003 元件直呼 `fetch` / `axios` 🟡** ≥ 3 處非 `lib/api/*` → 集中 RTK Query
- **R-FE-004 硬寫使用者語言 literal 🔵** → i18n key
- **R-FE-005 缺 Loading/Empty/Error 三態 🟡**
- **R-FE-006 送出按鈕未 disable 🟡**
- **R-FE-007 後端 error 直顯 🟡** → `error_code` 對應 i18n
- **R-FE-008 路由缺權限控制 🟠**
- **R-FE-009 客戶端用無 `NEXT_PUBLIC_*` / `VITE_*` 前綴 env 🔴**
- **R-FE-010 用 `any` 🟠** → `unknown` + 型別守衛
- **R-FE-011 不必要 re-render 🟡** — render 內字面值 / callback 未 `useCallback` / 列表元件未 `React.memo`
- **R-FE-012 用原生 `alert` / `confirm` / `prompt` 🟠** → `useDialog`
- **R-FE-013 build-time env 改值未重 build 🟡** — `NEXT_PUBLIC_*` / `VITE_*` 須重啟 dev server

## D. BE(FastAPI)

- **R-BE-001 路徑非 `/api/v{n}/*` 🟠** — 排除 `/health` / `/version` / `/api/docs`
- **R-BE-002 動詞命名 endpoint 🟡** → REST + kebab 複數
- **R-BE-003 Response 外殼不統一 🟠** → `ApiResponse{success,data,detail,response_code}`
- **R-BE-004 路由用 `dict` 當 response type 🟠** → Pydantic
- **R-BE-005 受保護 endpoint 缺 `Depends(require_*)` 🔴**
- **R-BE-006 仍用 `on_event` 🟡** → `lifespan`
- **R-BE-007 `docs_url` 不為 `/api/docs` 🟠**
- **R-BE-008 CORS `allow_origins=["*"]` + `allow_credentials=True` 🔴**
- **R-BE-009 回傳帶內部欄位 🟠** — `password_hash` / `deleted_at` → DTO 過濾
- **R-BE-010 無輸入驗證 🟠** → Pydantic Request schema
- **R-BE-011 `data` 直接為 array 🟠** → `{items: [...], total}`
- **R-BE-012 `detail` 洩漏內部 🔴** — SQL / traceback / table 名 → 通用訊息 + `code`
- **R-BE-013 缺 3 個 exception handler 🟠**
- **R-BE-014 跨層呼叫 🟡**
- **R-BE-015 第三方未集中 `clients/` 🟡**
- **R-BE-016 用 `Any` / `typing.List` / `typing.Dict` 🔵**
- **R-BE-017 函式缺型別標註 🔵**
- **R-BE-018 bcrypt 在 async 裸呼叫 🟠** → `asyncio.to_thread`
- **R-BE-019 多表寫入無 transaction 🟠** → `async with db.begin():`
- **R-BE-020 production 啟動無 fail-fast 🟠** — `Settings._fail_fast_in_prod`
- **R-BE-021 logger 未用 `exception` 🟡** — 用 `logger.error("...")` 丟 traceback
- **R-BE-022 測試 mock SQL 🟠** → 真 DB

## E. DB(PostgreSQL + SQLAlchemy)

- **R-DB-001 無 alembic 🟠**
- **R-DB-002 缺必備欄位 🟡** — `uid` / `is_deleted` / `created_at` / `updated_at` / `created_by` / `updated_by`
- **R-DB-003 密碼明文 / 弱雜湊 🔴** — 必 bcrypt / argon2
- **R-DB-004 SQL 字串拼接 🔴** → ORM / `text(...).bindparams()`
- **R-DB-005 金額 FLOAT/DOUBLE 🟠** → `Numeric(18, 2)` / 整數分
- **R-DB-006 無軟刪除 🟡**
- **R-DB-007 Binary 存 DB 🟠** → 物件儲存
- **R-DB-008 常查欄位無索引 🔵**
- **R-DB-009 Repository `find_by_uid` 不過濾 `is_deleted` 🟠** — 須預設過濾;不過濾版命名 `_including_deleted`
- **R-DB-010 SQLAlchemy 未繼承 `Base` / 未用 `mapped_column` 🔵**
- **R-DB-011 每請求建立連線 🟠** → `async_sessionmaker` 連線池
- **R-DB-012 Migration 修改既有 🔴** — 須建新 revision

## F. SEC

- **R-SEC-001 JWT `alg: none` 🔴** → HS256/RS256,secret ≥ 32
- **R-SEC-002 敏感端點無 rate limit 🟠** — `/login` / `/register` / `/forgot-password`
- **R-SEC-003 缺安全 headers 🟠** — CSP / X-Frame / X-Content-Type / HSTS
- **R-SEC-004 `eval` / `exec` 🔴**
- **R-SEC-005 密碼錯誤訊息洩露帳號 🟡**
- **R-SEC-006 檔案上傳無限制 🟠** — 副檔名白名單 + mime + 大小 + 隨機檔名
- **R-SEC-007 錯誤 response 洩漏內部 🟠**
- **R-SEC-008 權限只前端擋 🔴**
- **R-SEC-009 資源 ID 用序號 🔵** → UUID

## G. PII

- **R-PII-001 log 印 PII / 機密 🔴** — `password / token / email / phone / id_number / credit_card` → 遮罩
- **R-PII-002 PII 欄位無標註 🔵** — `comment="PII"`
- **R-PII-003 缺 audit log 🟠** — 登入 / 改密碼 / 匯出 / 權限變更須記錄

## H. LOG

- **R-LOG-001 缺 `/api/v1/health` 🟡** — 回 `{db}`
- **R-LOG-002 production debug log 開 🟠**
- **R-LOG-003 未接集中式 log 🟡** — Seq / ELK / Loki / Datadog
- **R-LOG-004 缺 graceful shutdown 🟠** — `lifespan` 須 `await engine.dispose()`
- **R-LOG-005 Log 缺結構化欄位 🟡** — `app_name` / `request_id` / ISO UTC
- **R-LOG-006 缺 `/api/v1/version` 🔵**

## I. GIT

- **R-GIT-001 `.env` / `node_modules` / `.venv` / build 產物被追蹤 🟠**
- **R-GIT-002 commit message 不符規範 🔵**
- **R-GIT-003 AI commit 缺 `(AI)` 🔵**

## J. TEST

- **R-TEST-001 無測試 🟡**
- **R-TEST-002 無 CI 🔵**
- **R-TEST-003 TS 未 strict 🔵**
- **R-TEST-004 後端 mock SQL 🟠**
- **R-TEST-005 第三方未用 `respx` / `MockTransport` 🔵**

## K. DEP(建置 / 依賴)

- **R-DEP-001 缺 lock file 🟠** — 無 `package-lock.json` / `uv.lock`
- **R-DEP-002 執行環境版本未 pin 🟡** — 無 `engines.node` / `requires-python`
- **R-DEP-003 套件版本浮動 🟠** — `^` / `~` / `*` / `>=`
- **R-DEP-004 未做依賴掃描 🔵** — CI 無 `npm audit` / `pip-audit`

---

## 報告格式

寫入 `docs/Tasks/scan-project/Issue-Scan-Project-{YYMMDDHHMMSS}.md`(12 位:年末兩碼 + 月日時分秒,UTC+8)。每次新檔,不覆寫。

**僅允許寫入報告檔**;**禁**修改其他檔;**禁**自動 git。

若違規記錄於 `fixed.md`,項目尾段附 `— 見 fixed.md §N` 並視為已處理。

章節順序:

0. **與前次差異**(僅當有舊報告) — 以 `R-xxx`/`AD-xxx` ID + 路徑為 key:🆕/✅/⏸/🔄
1. **總覽** — 時間 / 類別 / 🔴N 🟠N 🟡N 🔵N ⚪N / 結論
2. **專案摘要** — 目標 / 技術棧對照 / 目錄結構 / Task 進度 / 完成度
3. **詳細發現**(依嚴重度)
   ```
   ### 🔴 [R-ENV-001] 機密寫死
   - 檔案:`相對路徑:行號`
   - 內容 / 白話 / 修正(具體) / 首次發現:YYYY-MM-DD
   ```
4. **修正優先序** — 立刻 / 本週 / 有空
5. **已跳過類別**(必列原因)
6. **AD-xxx**(空可接受,須列已巡視面向)
7. **規範自身問題** — Design-Base 矛盾 / 缺漏

---

## Acceptance(必跑)

1. 報告檔已寫入 `docs/Tasks/scan-project/Issue-Scan-Project-{YYMMDDHHMMSS}.md`
2. 報告含全部 7 章節(總覽 / 摘要 / 詳細發現 / 優先序 / 跳過類別 / AD / 規範自身)
3. 每條 R-xxx / AD-xxx 含「相對路徑:行號」+ 具體修正建議
4. **禁**:修改任何非報告檔;**禁**:任何 git 操作
5. 若有舊報告 → 第 0 章「與前次差異」非空(🆕/✅/⏸/🔄)

---

## 自我約束

- 「相對路徑:行號」+ 修正具體到「改哪檔/第幾行/改成什麼」
- **不回報**:偏好性意見 / 規則換包裝 / 無後果風險 / 框架等效寫法
- 多違規先 🔴 + 🟠,結尾問「幫你修 Critical?」
- 僅寫入報告檔;**禁**修改其他檔或執行 git
