---
id: task-008
title: 補洞:secret 清單端點 + 前端密鑰紀錄改吃伺服器資料
status: done
worker: worker-G
parallel: false
depends_on: [task-005, task-006]
affected_files:
  - backend/app/api/v1/api_clients.py
  - backend/app/services/api_client_service.py
  - backend/app/schemas/api_client.py
  - backend/tests/test_api_clients_api.py
  - frontend/src/app/(main)/api-clients/page.tsx
  - frontend/src/lib/api/apiClientApi.ts
estimated_hours: 2
---

## 目標

補 task-005 拆解遺漏:前端密鑰管理需要「列出 client 底下所有 secret」的後端端點,否則重整後無法對既有密鑰做汰換,propose 對外承諾的「管理介面完成輪替全流程」不成立(task-006 完成註記已記錄此洞)。

## 規格

**後端**:
- 新增 `GET /api/v1/api-clients/{uid}/secrets`(admin-only,ApiResponse 殼):回傳該 client 全部**未軟刪** secret 的 `uid / status(active|retired) / created_at`,依 `created_at` 升冪;**永不回傳 `secret_hash` 與 pid**。client uid 不存在或已軟刪 → 404。
- `POST /api/v1/api-clients`(建立)與 `POST /{uid}/rotate-secret` 回應補 `secret_uid` 欄位(該把新發密鑰的 uid),讓前端能立即對應清單列。既有回應欄位不動(相容 task-006 已上線程式,僅新增欄位)。
- service 查詢比照 task-005 既有寫法(檔頭已註記 service 直下 select 的前例)。

**前端**:
- `apiClientApi.ts` 加 `listSecrets` endpoint(RTK Query,tag 失效:rotate / retire 後 refetch)。
- `page.tsx` 密鑰紀錄區改吃 `GET .../secrets` 伺服器資料(顯示建立時間走既有 datetime 顯示慣例 + 狀態),移除「僅本工作階段 local state 追蹤」的實作與其註記;汰換操作用清單裡的 `secret_uid`。
- 一次性明文 secret 面板行為不變(明文仍只在建立 / 輪替回應出現一次)。

## Acceptance

- [x] `cd backend && uv run pytest tests/test_api_clients_api.py` 全綠(新增:清單含 active+retired 且欄位僅 uid/status/created_at、無 secret_hash/pid;建立與 rotate 回應含 secret_uid 且與清單對得上;不存在 uid → 404)
- [x] `uv run pytest` 全套全綠;`uv run ruff check app tests` + `uv run mypy app` 無新增錯誤
- [x] `cd frontend && npm run lint` + `npx tsc --noEmit` + `npm run build` 三項乾淨
- [x] 真實 API 驗證:建立 client → rotate 一把 → `GET .../secrets` 回 2 筆(1 active 初始 + 1 active 新發或依實作 2 active)→ retire 其中一把 → 清單該筆 status=retired;前端頁面重整後仍能對既有密鑰執行汰換(等效 API 驗證可)

## 完成註記(worker-G,2026-07-30)

**後端**
- `GET /api/v1/api-clients/{uid}/secrets`(admin-only):`ApiResponse[ApiClientSecretListResponse]`,`{items:[{uid,status,created_at}], total}`,依 `created_at, pid` 升冪(同秒多列以 pid 定序);client 不存在 / 已軟刪 → 404。
- 清單查詢落在 `ApiClientService.list_secrets`(需含 retired,`api_client_repo.list_active_secrets` 不夠用;repo 檔不在白名單 → 依檔頭既有前例直下 select,檔頭註記同步補「含 retired 的密鑰清單」)。
- `ApiClientCreatedResponse` 新增 `secret_uid`(初始密鑰);`ApiClientSecretIssuedResponse` 原本就有 `secret_uid`,未動。既有欄位零變動,相容 task-006 已上線程式。
- 新增 schema:`ApiClientSecretResponse` / `ApiClientSecretListResponse`(永不含 `secret_hash` / `pid`)。

**前端**
- `apiClientApi.ts`:新增 `listApiClientSecrets` query(tag `ApiClient/SECRETS-<uid>`);rotate / retire 改為同時失效 `LIST` 與該 client 的 `SECRETS-<uid>` → 汰換後清單自動 refetch;`CreateApiClientResult` 補 `secret_uid`。
- `page.tsx`:刪除 `KnownSecret` local state(`knownSecretsByClient`)與「僅本工作階段」文案 / `KnownSecretItem`,改為展開時掛載 `SecretHistoryPanel` 走伺服器資料(顯示 `formatDateTime(created_at)` + 有效 / 已汰換);汰換以清單列 `uid` 呼叫;汰換確認對話框改以核發時間指稱密鑰。一次性明文面板行為不變。

**驗證**
- `pytest tests/test_api_clients_api.py` 18 passed;全套 `pytest` 415 passed;`ruff check app tests` 乾淨;`mypy app` 僅剩既有 `schedule_repo.py:528` 一筆(未動該檔,非新增)。
- 前端 `npx tsc --noEmit` / `npm run lint` / `npm run build` 三項乾淨。
- 真實 API(docker compose,已重建 backend + frontend):建立回 `secret_uid=baf877c7…`;rotate 回 `85a4d513…`、`active_secret_count=2`;`GET .../secrets` → `total=2` 兩筆皆 active 且僅 `uid/status/created_at`;retire 初始密鑰後同一列轉 `retired`、另一列仍 active;未知 uid → 404。**初始密鑰現可直接汰換**(原洞:前端只能對本工作階段輪替過的密鑰動作)。驗證用 client 已全數汰換密鑰並 `status=disabled`。

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
