# Tasks v1.6.0

> 狀態:進行中(已完成 1/7;001 done,002=worker-B 執行中)

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | api_client_users + api_client_secrets 資料表(models + migration + repo) | done(worker-A) | ✓ | — | `backend/app/models/api_client_user.py` / `api_client_secret.py` / `models/__init__.py` / `alembic/versions/v8_add_api_client_users.py` / `repositories/api_client_repo.py` / `tests/test_api_client_models_repo.py` |
| 002 | api_client_router 骨架 + 統一封套 + JWT 簽發/驗簽 + /api/client 掛載 | in_progress(worker-B) | ✓ | — | `backend/app/api_client_router/*`(骨架全新檔)/ `core/config.py` / `main.py` / `tests/test_api_client_router_core.py` |
| 003 | per-Client Rate Limit(雙窗口)+ 連續失敗鎖定(Redis,fail-open) | pending | ✓ | 002 | `backend/app/api_client_router/common/rate_limit.py` / `tests/test_api_client_rate_limit.py` |
| 004 | POST /api/client/v1.0/token + /refresh_token 端點業務流 | pending | ✗ | 001, 002, 003 | `backend/app/api_client_router/versions/v1_0.py` / `common/auth.py` / `common/schemas.py` / `tests/test_api_client_token_api.py` |
| 005 | 後台管理 API /api/v1/api-clients(建立/發證/輪替/啟停/限流參數) | pending | ✓ | 001 | `backend/app/api/v1/api_clients.py` / `api/v1/__init__.py` / `services/api_client_service.py` / `schemas/api_client.py` / `tests/test_api_clients_api.py` |
| 006 | 前端「API Client 設定」sidebar 區塊 + 管理頁 | pending | ✓ | 005 | `frontend/src/components/layout/Sidebar.tsx` / `app/(main)/api-clients/page.tsx` / `lib/api/apiClientApi.ts` |
| 007 | e2e 驗證 + Arch 文件回寫 + 收口文件 | pending | ✗ | 001–006 | `docs/Tasks/v1.6.0/verification-v1.6.0.md` / `docs/Arch/datahub-api-gateway-arch.html` |

## 拆解摘要

- **總量**:7 個 task,預估 ~25 hr。
- **並行波次**:
  - 第 1 波:**001 ∥ 002**(DB 地基與 router 骨架無共檔)。
  - 第 2 波:**003 ∥ 005**(003 等 002 的套件骨架;005 只等 001,走 `api/v1/__init__.py` 註冊、不碰 `main.py`,與 002 無共檔)。
  - 第 3 波:**004 ∥ 006**(004 組裝端點業務流;006 串 005 的管理 API)。
  - 收尾:**007**(全數 done 後 e2e + Arch 回寫)。
- **關鍵路徑**:`002 → 003 → 004 → 007`(~14 hr)。
- **同檔互鎖**:004 改 002 建的 `v1_0.py` / `auth.py` → 以 depends 序列化;005 動 `api/v1/__init__.py`、002 動 `main.py`,兩者分離無衝突;其餘全新檔。
- **In Scope 對映**(無 orphan):`/token`、`/refresh_token` → 004;`api_client_users` 表 → 001;管理(後端 API / 前端介面)→ 005 / 006;Rate Limit 參數化 → 001(欄位)+ 003(執行)+ 005(編輯)+ 006(UI);JWT 驗簽共用依賴 → 002;路由命名空間 → 002;token 端點抗壓 → 003 + 004;錯誤碼與封套 → 002 + 004。
- **阻塞點**:002 是 003 / 004 的前置(關鍵路徑頭);005 是 006 唯一前置;007 需本地 docker compose(Redis + PG)可起的環境。
- **拆解註記(請 user 留意)**:限流雙窗口以 **ZSET 滑動窗口單 key** 實作,key 名恰為裁定的 `rate_limit:client:<client_id>`(不加窗口後綴);連續失敗鎖定門檻拆解定為 **5 次失敗鎖 300 秒**(propose 未定數值,不同意請改 task-003)。
- **派工建議**(model 分級,保守取高):001 opus·medium / 002 opus·high / 003 opus·high / 004 opus·high / 005 opus·medium / 006 sonnet·high / 007 sonnet·medium。

## 執行前置(worker 認領前必讀)

- **分支**:`dev-v1.6.0`(自 dev-v1.5.2/schema-drift e78156d 切出,已推 origin + df-it)。
- **跑法**:改碼後以 `docker compose up -d --build` 驗證,**禁** start-dev(會打掛 Docker Desktop engine)。
- **底線**:禁任何 DROP 類操作(migration downgrade 僅限撤銷本版新表);secret / JWT 金鑰禁明文入版控;RDS 時間一律 naive timestamp(UTC+8)。
- **協議**:認領 task 改 `status: in_progress` + 在本檔註記 worker id;Acceptance 全過才標 done;commit 帶 `[task-NNN]` tag。
- 全數 done 後:`/scan-project` → 修 → `/reflect-rules` → 收口。
