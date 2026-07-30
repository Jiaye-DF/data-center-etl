---
id: task-009
title: secret 可逆加密+儀表板明文檢視+全頁文案使用者化(user 裁定追加)
status: done
worker: worker-I
parallel: false
depends_on: [task-007, task-008]
affected_files:
  - backend/pyproject.toml
  - backend/uv.lock
  - backend/app/core/config.py
  - backend/app/core/security.py
  - backend/alembic/versions/v9_add_secret_encrypted.py
  - backend/app/models/api_client_secret.py
  - backend/app/services/api_client_service.py
  - backend/app/api/v1/api_clients.py
  - backend/app/schemas/api_client.py
  - backend/tests/test_api_clients_api.py
  - frontend/src/app/(main)/api-clients/page.tsx
  - frontend/src/lib/api/apiClientApi.ts
estimated_hours: 4
---

## 目標

v1.6.0 收口後 user 追加裁定(2026-07-30):
1. **client_secret 改可逆加密儲存,admin 可在儀表板隨時檢視明文**(推翻原「明文僅一次性顯示」對外承諾與 `03-passwords-and-pii` 只存雜湊原則——user 明示裁定,理由:僅 admin 可及)。
2. **每一個 API Client = 一個使用者**:全頁文案以「使用者」為主體。

## 規格

**後端**:
- `pyproject.toml` 顯式鎖定 `cryptography==49.0.0`(既有轉依賴,無新安裝;`uv lock` 同步)。
- config 新增 `CLIENT_SECRET_ENCRYPTION_KEY`(Fernet key,必填 fail-fast,比照 `CLIENT_JWT_SECRET` 寫法與 env 五處注入:根 `.env`、`backend/.env`、三個 example 檔;dev 用固定示例 Fernet key,production example 留空)。加解密 helper 放 `core/security.py`(比照既有 bcrypt helper 風格;Fernet 操作輕量,不需 to_thread)。
- migration `v9_add_secret_encrypted.py`:`api_client_secrets` **ADD COLUMN** `secret_encrypted TEXT NULL`(只加不刪;既有列為 NULL = 舊密鑰無明文可顯示);model 同步。
- service:`create_client` / `rotate(add_secret)` 同時存 bcrypt 雜湊(驗證用,**token 驗證路徑零變動**)與 Fernet 加密明文。
- 新端點 `GET /api/v1/api-clients/{uid}/secrets/{secret_uid}/reveal`(admin-only,ApiResponse 殼):回 `{client_secret}` 解密明文;該列 `secret_encrypted` 為 NULL → `409` + detail 提示輪替重發;client/secret 不存在或軟刪 → 404。**每次 reveal 寫 audit log**(`api_client_secret_reveal`,detail 禁含明文)。
- secrets 清單回應每列加 `revealable: bool`(既有欄位不動)。

**前端**(風格照本頁既有寫法):
- 表格新增「Secret」欄:顯示最新 active 密鑰,預設遮罩 `••••••••`+「顯示」鈕 → 呼 reveal 取明文(揭露+複製按鈕,可再遮回);`revealable=false` → 顯示「舊密鑰,輪替後可檢視」。展開的密鑰面板每列同樣提供 reveal(revealable 才有)。reveal 結果僅存元件 state,不進 RTK cache(避免明文長駐快取)。
- 文案使用者化:副標改「管理使用者的 API 存取憑證(admin 專用)」;表頭「名稱」→「使用者」;建立 dialog 標題「建立使用者 API 權限」、名稱欄 label「使用者名稱」;其他出現「應用系統」主體的文案一律改以「使用者」為主體。「建立使用者 API 權限」按鈕與副標已先改好,勿回退。
- 一次性 secret 面板保留(建立/輪替當下仍即時顯示)。

**文件同步(本 task 內完成)**:
- `docs/Arch/datahub-api-gateway-arch.html`:「secret 只存雜湊 · 明文僅發放時顯示一次」相關文字(chip 與詳細表格)改為「secret 可逆加密儲存,僅 admin 後台可檢視明文」;僅此一類改動。
- `docs/Tasks/v1.6.0/propose-v1.6.0.md` 底部新增 `## 變更紀錄` 區塊:2026-07-30 user 裁定 secret 改可逆加密+儀表板明文檢視(推翻對外承諾「僅一次性顯示」與 03-passwords-and-pii 適用範圍),及文案使用者化;此為收口後追加,由 task-009 落地。

## Acceptance

- [x] `cd backend && uv run alembic upgrade head` 成功且 downgrade round-trip OK
- [x] `uv run pytest tests/test_api_clients_api.py` 全綠(新增:建立後 reveal 回明文且與建立回應一致;舊列(手動塞 NULL)reveal → 409;非 admin reveal → 403;audit 有 reveal 事件且 detail 無明文;清單含 revealable)
- [x] `uv run pytest` 全套全綠;ruff + mypy 無新增錯誤
- [x] `cd frontend && npm run lint` + `npx tsc --noEmit` + `npm run build` 三項乾淨
- [x] 真實 API:建立使用者 → 表格 reveal 拿到明文 → 用該明文打 `/api/client/v1.0/token` 取證成功(證明加密存的明文與雜湊驗證一致)
- [x] 頁面文案 grep 不到「應用系統」主體殘留(僅限本頁)

## 完成註記(2026-07-30,worker-I)

**Acceptance 逐條結果**

1. migration:`v9_add_secret_encrypted`(`down_revision=v8`)`upgrade head` → `downgrade -1` → `upgrade head` 三段皆成功,`alembic current` = `v9 (head)`;downgrade 僅 `drop_column` 本次新增欄。
2. `pytest tests/test_api_clients_api.py`:**25 passed**(新增 7 支 reveal 測試 + 既有欄位集合斷言補 `revealable`)。
3. `pytest` 全套:**422 passed**;`ruff check .` All checks passed;`mypy app` 僅既有 1 錯(`schedule_repo.py:528`),`tests` 錯誤數與改動前相同(無新增)。
4. 前端 `npm run lint` / `npx tsc --noEmit` / `npm run build` 三項乾淨。
5. 真實 API(docker compose 重建 backend + frontend):建立 → secrets 清單 `revealable=true` → reveal 200 且明文與建立回應**完全一致** → 以該明文打 `POST /api/client/v1.0/token` 回 **200**(`token_type=Bearer`、`expires_in=900`、JWT `sub`=client_id、`iss=datahub-api-gateway`);audit 有 `api_client_secret_reveal` 且 detail 不含明文;dev DB 既有 11 筆舊列 `secret_encrypted IS NULL` → reveal 回 **409**「此密鑰核發時未保存可檢視明文…」、清單 `revealable=false`;入庫值為 Fernet 密文(`gAAAAA…`,140 字元),非明文。
6. 頁面 `應用系統` grep = 0。

**偏離/補充說明**

- env 注入實際為 **6 處**(task 檔寫「五處」):根 `.env`、`backend/.env`、`.env.example`、`.env.development.example`、`.env.staging.example`、`.env.production.example`——repo 有 4 個 example 檔,依 `00-overview/02-secrets.md`「新增 secret 欄位 → `.env*.example` 全層同步」全部補齊。dev 用固定示例 Fernet key,staging 用 `__GENERATE_AT_DEPLOY__`,`.env.example` / production example 留空。
- `secret_encrypted` 由 service 於 `repo.add_secret()` 回傳後直接指派再 flush(新增私有 `_issue_secret`),因 `api_client_repo.py` 不在白名單、無法擴 `add_secret` 參數;已於程式碼註記原因。
- 一次性面板保留但更名 `SecretRevealPanel` → `IssuedSecretPanel`(避免與新的 reveal 概念混淆),文案由「關閉後將不再顯示」改為「關閉後仍可在清單『Secret』欄重新檢視」。
- 前端 reveal 走 `build.mutation`(後端仍是 GET)+ 呼叫後立即 `reset()`,確保明文只留元件 state、不進 RTK 快取。
- 表格 Secret 欄以 `useListApiClientSecretsQuery(client.uid)` 取該列最新 active 密鑰(與展開面板共用同一快取項);表寬 `min-w-[960px]` → `min-w-[1120px]`。
- h1「API Client 設定」與 sidebar nav label 一致,故未動(`Sidebar.tsx` 不在白名單)。
- **部署待辦**:staging / production 須注入 `CLIENT_SECRET_ENCRYPTION_KEY`(缺值 fail-fast);另 `docker-compose-staging.yml` / `-production.yml` 的 backend `environment` 目前只顯式傳 `JWT_SECRET_KEY`,`CLIENT_JWT_SECRET` 與本次新 key 皆未列(v1.6.0 收口既有遺留,compose 檔不在本 task 白名單,未動)。
- dev DB 留有 3 筆「task-009 驗證使用者」測試 Client(供 UI 人工複測 reveal 按鈕),未清除。

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/04-databases/03-passwords-and-pii.md`
- `docs/Design-Base/04-databases/08-alembic.md`
- `docs/Design-Base/00-overview/02-secrets.md`
- `docs/Design-Base/02-frontend/00-overview.md`
