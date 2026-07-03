---
id: task-013
title: Coolify 部署 EC2 + RDS 端到端驗收(版本收口)
status: pending
parallel: false
depends_on: [task-008, task-010, task-011, task-012]
affected_files:
  - README.md
  - docs/Tasks/v1.1.0/deploy-runbook.md
estimated_hours: 3
---

## 目標

版本驗收收口:Coolify 部署到 EC2(全部 `etl_` image),EC2 連 RDS 完成一次真實 ETL 寫入,並依 propose 驗收標準逐條驗證。產出部署 runbook(env 對照 + 步驟 + 驗收清單);需 AWS / Coolify 憑證的項目屬**人工驗收**,agent 不造假輸出。

## 範圍要點

- runbook 內容:Coolify 服務建立(frontend / backend / worker / scheduler / redis;自有 DB 用 RDS 或 EC2 容器擇一並記錄決策)、環境變數分層對照表(development / production,`03-env-layers.md`)、EC2 → RDS Security Group 放行檢查步驟、init_admin 設定、驗收指令清單。
- **禁**把 `.env.development` 值帶上部署(CLAUDE.md localhost ≠ 部署環境)。
- 執行發現 bug → 回寫對應 task 並記 `fixed.md`,不在本 task 內修程式。

## Acceptance

> 以下需 Coolify / AWS / RDS 憑證,屬人工驗收;由執行者依 runbook 逐條回填。

- [ ] Coolify 各服務部署成功,backend health endpoint 回 200
- [ ] 後台以 env 注入之 init_admin 本地登入成功;DF-SSO 登入成功
- [ ] 手動觸發一次 ETL:run 成功、`erp_etl_hub_test` 資料落地、`etl/scripts/verify_target_db.sql` 驗證每欄位 Comment 非空
- [ ] 建一筆近期排程,到點自動執行且後台可查逐表詳細 log
- [ ] 停用一表後再執行,該表 skipped 且 log 可證
- [ ] viewer 帳號寫入類操作被拒(403 / UI 隱藏)
- [ ] `git diff --stat` 不含 `etl/` 既有檔案異動(Glue 版凍結)
- [ ] (可本地驗)runbook 存在且含 env 對照表:`grep -q "SOURCE_DB_HOST" docs/Tasks/v1.1.0/deploy-runbook.md`

## 必讀檔(Just-in-time)

- `docs/Design-Base/06-Coolify-CD/00-overview.md` + `04-env-and-secrets.md` + `05-deploy-flow.md`
- `docs/Design-Base/00-overview/03-env-layers.md`
- `docs/Design-Base/99-code-review/00-overview.md` + `03-pr-self-check.md`(版本收口 gate)
