---
id: task-007
title: e2e 驗證 + Arch 文件回寫 + 收口文件
status: pending
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

- [ ] `[ -f docs/Tasks/v1.6.0/verification-v1.6.0.md ]` 且逐條含實際執行命令與結果(非「應通過」字樣)
- [ ] propose「驗收標準」每一條在 verification 有對應段落與判定(過 / 不過 / 環境受限待補,不過項須開 fixed.md)
- [ ] `cd backend && uv run pytest` 全綠、`uv run ruff check app tests` + `uv run mypy app` 乾淨;`cd frontend && npm run build` 成功
- [ ] `docs/Arch/datahub-api-gateway-arch.html` 內 `grep` 不到 `api_clients`(獨立表名語意)與 `rl:` 前綴殘留(僅限上述兩處決策相關文字;其他內容 diff 為零)
- [ ] `tasks-v1.6.0.md` 頂部狀態行更新為全數完成

## 必讀檔(Just-in-time)

- `docs/Design-Base/99-code-review/00-overview.md`
- `docs/Design-Base/99-code-review/03-pr-self-check.md`
- `docs/Design-Base/03-backend/07-testing.md`
