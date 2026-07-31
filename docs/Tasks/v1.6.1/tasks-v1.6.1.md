# Tasks v1.6.1

> 狀態:進行中(8/11 done)

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | RDS `client_setting` schema + 12 張權限表 DDL + models | done | ✓ | — | `backend/app/models/client_setting.py` / `backend/app/etl/client_setting_schema.py` / `backend/tests/test_client_setting_schema.py` |
| 002 | 權限資料存取層 repository(RDS 直讀寫 + 綁定防呆查詢) | done | ✗ | 001 | `backend/app/repositories/client_setting_repo.py` / `backend/tests/test_client_setting_repo.py` |
| 003 | Redis 讀取快取層(cache-aside + 異動失效 + 降級直讀) | done | ✗ | 002 | `backend/app/services/permission_cache.py` / `backend/tests/test_permission_cache.py` |
| 004 | 系統別 / 作業管理 API(CRUD + 範圍 items + semantic 驗證) | done | ✗ | 002, 003 | `backend/app/api/v1/client_settings.py` / `backend/app/api/v1/__init__.py` / `backend/app/services/client_setting_service.py` / `backend/app/schemas/client_setting.py` / `backend/tests/test_client_settings_services_api.py` |
| 005 | 設定檔 / Role 管理 API(勾作業 + 授權矩陣 + 必綁防呆) | done | ✗ | 004 | `backend/app/api/v1/client_settings.py` / `backend/app/services/client_setting_service.py` / `backend/app/schemas/client_setting.py` / `backend/tests/test_client_settings_profiles_api.py` |
| 006 | 特例權限 + API Client 指派 API(可重用組 + 效期綁定) | done | ✗ | 005 | `backend/app/api/v1/client_settings.py` / `backend/app/services/client_setting_service.py` / `backend/app/schemas/client_setting.py` / `backend/tests/test_client_settings_exceptions_api.py` |
| 007 | 預覽端點 effective-permissions(聯集 ∩ 範圍,default-closed,走快取) | done | ✓ | 002, 003 | `backend/app/services/effective_permission_service.py` / `backend/app/api/v1/api_clients.py` / `backend/app/schemas/client_setting_preview.py` / `backend/tests/test_effective_permissions.py` |
| 008 | 前端 API 層 + 權限管理頁骨架(併入 API Client nav 區塊) | done | ✗ | 004, 005, 006 | `frontend/src/lib/api/clientSettingApi.ts` / `frontend/src/components/layout/Sidebar.tsx` / `frontend/src/app/(main)/client-settings/page.tsx` |
| 009 | 前端授權管理 UI(系統別 / 作業範圍 / 設定檔矩陣 / Role / 特例) | pending | ✗ | 008 | `frontend/src/app/(main)/client-settings/page.tsx` / `frontend/src/lib/api/clientSettingApi.ts` |
| 010 | 前端 API Client 頁整合(Role 指派 + 特例綁定 + 權限檢視) | pending | ✗ | 007, 008 | `frontend/src/app/(main)/api-clients/page.tsx` / `frontend/src/lib/api/apiClientApi.ts` |
| 011 | e2e 收口 + 稽核驗證 + verification 文件 + Arch 回寫 | pending | ✗ | 001–010 | `docs/Tasks/v1.6.1/verification-v1.6.1.md` / `docs/Arch/datahub-api-gateway-arch.html` |

## 拆解摘要

- **總量**:11 個 task,預估 ~34 hr。
- **並行波次**:
  - 第 1 波:**001**(唯一地基,無前置)。
  - 第 2 波:**002**(repo 吃 001 的 models / schema)。
  - 第 3 波:**003 ∥ 007 起步**(003 快取層;007 只依賴 002+003,與 004–006 鏈無共檔,003 完成後即可並行)。
  - 第 4 波:**004 → 005 → 006**(三者同動 `client_settings.py` / `client_setting_service.py` / `schemas/client_setting.py` → 同檔互鎖,強制序列化)。
  - 第 5 波:**008 → 009 ∥ 010**(008 建前端 API 層與骨架;009 管理 UI 與 010 API Client 頁整合分屬不同檔,可並行)。
  - 收尾:**011**(全數 done 後 e2e + Arch 回寫)。
- **關鍵路徑**:`001 → 002 → 003 → 004 → 005 → 006 → 008 → 009`(~24 hr)。
- **同檔互鎖**:004 / 005 / 006 共用三個後端檔 → 依賴鏈序列化;008 / 009 共用 `clientSettingApi.ts` 與 `client-settings/page.tsx` → 序列化;010 只動 api-clients 兩檔與 009 無共檔 → 並行;007 動 `api/v1/api_clients.py` 與 004–006 的 `__init__.py` 註冊無共檔(`client_settings.py` 路由於 004 註冊一次)。
- **In Scope 對映**(無 orphan):11 張表 / client_setting schema → 001 + 002;系統別 / 作業管理 → 004 + 008 + 009;設定檔管理 → 005 + 009;Role 管理 → 005 + 009;API Client 指派 → 006 + 010;預覽 → 007 + 010;Redis 快取層 → 003(004–007 讀路徑掛用);加法模型 → 004–007 語意 + 007 測試鎖定;稽核 → 004 / 005 / 006 / 007 各寫端點 + 011 驗證。
- **阻塞點**:001 是全部的根;004–006 鏈是後端最長段;008 是全部前端的前置;011 需本地 docker compose(Redis + PG)+ 可連 RDS 的環境。
- **拆解註記(請 user 留意)**:
  - 表數勘誤:propose / tasks 原寫「11 張」,但兩份文件的表名列舉皆為 **12 個**(與 ERD 一致;特例組 4 表被誤算 3)。task-001 依列舉實作 12 張,本檔已更正。
  - 權限表 **DDL 不走自有 DB alembic**,比照 `semantic_schema.py` 前例以「啟動 / 指令時 ensure schema + 表存在」方式建置(`CREATE SCHEMA IF NOT EXISTS client_setting` + `CREATE TABLE IF NOT EXISTS`),冪等可重跑。
  - 快取 key 前綴拆解定為 **`client_setting:`**(如 `client_setting:effective:<client_uid>`),TTL 預設 **300s**(propose 未定數值,不同意請改 task-003)。
  - 管理端點路徑拆解定為 `/api/v1/client-settings/*`(系統別 / 作業 / 設定檔 / Role / 特例統一掛此前綴,與既有 `/api/v1/roles`(後台人角色)明確區隔);預覽維持裁定的 `GET /api/v1/api-clients/{uid}/effective-permissions`。
- **派工建議**(model 分級,保守取高):001 opus·medium / 002 opus·medium / 003 opus·high / 004 opus·medium / 005 opus·high / 006 opus·medium / 007 opus·high / 008 sonnet·high / 009 opus·medium / 010 sonnet·high / 011 sonnet·medium。

## 執行前置(worker 認領前必讀)

- **分支**:`dev-v1.6.1`(自 main 切出,propose 定稿 commit 5a7f097,已推 origin)。
- **跑法**:改碼後以 `docker compose up -d --build` 驗證,**禁** start-dev(會打掛 Docker Desktop engine)。
- **底線**:禁任何 DROP 類操作;RDS 寫入僅限 `client_setting` schema 新表;RDS 時間一律 naive timestamp(UTC+8,`06-timezone`);機密走 env 注入。
- **RDS 連線**:沿用既有 `rds_database_url(RDS_TARGET_DB_ENV)` + `create_async_engine` 模式(見 `etl/introspect.py` / `semantic_schema.py` 前例);本地開發需 `.env` 具備 RDS 連線資訊。
- **協議**:認領 task 改 `status: in_progress` + 在本檔註記 worker id;Acceptance 全過才標 done;commit 帶 `[task-NNN]` tag。
- 全數 done 後:`/scan-project` → 修 → `/reflect-rules` → 收口。
