---
id: task-007
title: e2e 驗證 + Arch 文件回寫 + 收口文件
status: done
worker: worker-H
parallel: false
depends_on: [task-001, task-002, task-003, task-004, task-005, task-006]
affected_files:
  - docs/Tasks/v1.6.0/verification-v1.6.0.md
  - docs/Arch/datahub-api-gateway-arch.html
estimated_hours: 3
---

## 目標

對 propose 驗收標準逐條 e2e 驗證並產出 `verification-v1.6.0.md`(格式比照 `docs/Tasks/v1.5.2/verification-v1.5.2.md`);同步回寫 Arch 文件中被本版決策推翻的兩處。

## 規格

**e2e 驗證(本地 docker compose,逐條記錄命令與輸出)**:
1. 後台建 Client → `POST /api/client/v1.0/token` 200,解 JWT 驗 `sub` / `exp-iat=900` / `expires_in=900`。
2. 錯 secret / 不存在 client_id / 停用 Client → 三者 401 回應 JSON 全等(無法區分)。
3. Rate Limit:迴圈打 `/token` 第 31 次(60s 內)→ 429 + `Retry-After`;`redis-cli` 確認 key 恰為 `rate_limit:client:<client_id>`;後台 PATCH 調高 `rate_limit_per_minute` → 立即放行。
4. 連續 5 次錯 secret → 429 鎖定;等 300s(或測試環境縮短 TTL 佐證)自動解鎖。
5. `/refresh_token` 四情境(過期換新 200 / 簽章壞 401 / sub 不符 401 / secret 錯 401)。
6. secret 輪替:兩把並存皆可取證 → 汰舊後舊 secret 401。
7. 封套:上述所有回應四欄齊全(`success / response_code / detail / data`),`detail` 無內部設計字樣。
8. 前端手測(task-006 清單)結果彙整;既有 `/api/v1` 迴歸(全套 pytest + 抽測 users / roles 頁)。

**Arch 文件回寫(`docs/Arch/datahub-api-gateway-arch.html`,僅兩處決策同步,禁順手重構)**:
- ERD 與內文表名 `api_clients` → **`api_client_users`**(+ 註記 secret 拆 `api_client_secrets` 子表)。
- 限流 key 慣例 `rl:` 前綴 → **`rate_limit:client:<client_id>`**;並補「參數存 DB(30/分、200/10 分預設)、後台可調」一句。

## Acceptance

- [x] `[ -f docs/Tasks/v1.6.0/verification-v1.6.0.md ]` 且逐條含實際執行命令與結果(非「應通過」字樣)
- [x] propose「驗收標準」每一條在 verification 有對應段落與判定(過 / 不過 / 環境受限待補,不過項須開 fixed.md)
- [x] `cd backend && uv run pytest` 全綠、`uv run ruff check app tests` + `uv run mypy app` 乾淨;`cd frontend && npm run build` 成功
- [x] `docs/Arch/datahub-api-gateway-arch.html` 內 `grep` 不到 `api_clients`(獨立表名語意)與 `rl:` 前綴殘留(僅限上述兩處決策相關文字;其他內容 diff 為零)
- [x] `tasks-v1.6.0.md` 頂部狀態行更新為全數完成

## 必讀檔(Just-in-time)

- `docs/Design-Base/99-code-review/00-overview.md`
- `docs/Design-Base/99-code-review/03-pr-self-check.md`
- `docs/Design-Base/03-backend/07-testing.md`

## 完成註記(worker-H)

### 驗證結果總覽

- `uv run pytest` → **415 passed**;`uv run ruff check app tests` → All checks passed;`uv run mypy app` → 僅既有 `schedule_repo.py:528` 一筆(非新增);`cd frontend && npm run build` → 成功。
- 整合驗證(docker compose 真實 HTTP,`etl_backend` 對 dev DB `data_center_etl`):propose 驗收標準逐條實測,建 2 個測試 Client(`v160-e2e-worker-h` / `-B`)完整跑過取證 / 401 同構三情境 / 雙窗口限流(第 6 次 429、10 分鐘窗第 11 次 429,已用 `PATCH` 調低額度縮短驗證時間並註記方法)/ redis key 格式 `rate_limit:client:<client_id>` / 後台調高即生效 / 連續 5 次失敗鎖定 429(縮短 TTL 佐證自動解鎖)/ `/refresh_token` 四情境 / secret 輪替並存與汰舊 / 封套四欄。逐條命令與輸出見 `docs/Tasks/v1.6.0/verification-v1.6.0.md`。
- 全數 PASS,僅前端純 UI 呈現項(繼承 task-006 待複測清單)標記「環境受限待補」,無「不過」項,未開 `fixed.md`。
- 測試用 Client 驗畢皆已停用 + 密鑰全數汰換(無 DELETE / 無清 DB)。

### Arch 文件回寫

`docs/Arch/datahub-api-gateway-arch.html` 僅兩類決策同步(diff 5 hunk):
1. `api_clients` → `api_client_users`(模組②方塊圖 1 處 + ERD 關聯線 2 處 + ERD 實體標頭 1 處),ERD `secret_hash` 欄位說明同步改為「已拆至 `api_client_secrets` 子表(雙鑰輪替)」。
2. 限流 key `rl:` 前綴 → `rate_limit:client:<client_id>`,補「參數存 DB(預設 30/分、200/10 分),後台可逐 Client 調整」一句。
`grep "api_clients\b"` / `grep "rl:"` 對該檔皆零命中;其餘內容零異動。

### 殘留事項(詳見 verification 文件)

`.env.staging`/`.env.production` 部署前須生成 `CLIENT_JWT_SECRET`;task-006 UI 純視覺項待人工複測;PATCH `description` 無法清空(既有語意,非缺陷);4 項 reflect 候選(對外版本層直呼 repository / retire 三層路徑 / `ClientEnvelopeRoute` 位置建議挪至 `common/`)待集中決議。
