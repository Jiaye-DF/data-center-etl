---
id: task-010
title: 追加修正:單一密鑰制(發新即撤舊)+限流欄位合併+清測試資料(user 裁定)
status: done
worker: orchestrator(主線接手,worker-J 三度 529 中斷)
parallel: false
depends_on: [task-009]
affected_files:
  - backend/app/repositories/api_client_repo.py
  - backend/app/services/api_client_service.py
  - backend/app/api/v1/api_clients.py
  - backend/app/schemas/api_client.py
  - backend/tests/test_api_client_models_repo.py
  - backend/tests/test_api_clients_api.py
  - backend/tests/test_api_client_token_api.py
  - frontend/src/app/(main)/api-clients/page.tsx
  - frontend/src/lib/api/apiClientApi.ts
  - docs/Arch/datahub-api-gateway-arch.html
  - docs/Tasks/v1.6.0/propose-v1.6.0.md
estimated_hours: 3
---

## 目標

user 裁定三項修正(2026-07-30,推翻原「雙 secret 並存輪替」設計):
1. **單一密鑰制**:每個使用者同時只允許 **1 把 active** 密鑰;輪替 = 發新的**同交易自動 retire 舊的**(立即失效,無並存過渡期)。
2. **限流 UI 合併**:每分鐘 / 每 10 分鐘上限仍為 per-User DB 參數(功能不變),但表格**不佔兩個欄位**——合併為單一「流量上限」欄(如 `30 / 分 · 200 / 10 分`);編輯 dialog 仍兩個輸入框分開設定。
3. **清空目前測試資料**:開發 DB 內所有 `api_client_users`(含其 secrets)一律軟刪(`is_deleted=true`,禁物理 DELETE),供 user 改完後重新測試。

## 規格

**後端**:
- rotate(add_secret)語意改為「發新即撤舊」:同一 DB session 內先將該使用者所有 active secret 改 `retired`,再插入新 active 列;**不再有 2 把上限檢核與 409**(相關程式與測試移除)。
- `create_client` 不變(建立時發第 1 把)。
- 獨立 retire 端點(`POST /{uid}/secrets/{secret_uid}/retire`)保留(admin 可手動撤銷唯一一把使該使用者無法取證)。
- 清單 / reveal / revealable 行為不變(歷史 retired 列仍在清單)。
- schema 若有 `active_secret_count` 相關欄位保留(值恆 0 或 1)。
- audit:rotate 事件 detail 註記「舊密鑰已自動撤銷」(禁明文)。

**前端**:
- 表格:移除「每分鐘上限」「每 10 分鐘上限」兩欄,合併為單一「流量上限」欄(格式 `30 / 分 · 200 / 10 分`);「有效密鑰數」欄可一併移除(恆 1,無資訊量)——如版面已含 Secret 欄(task-009),最終欄序:使用者 / Client ID / Secret / 狀態 / 流量上限 / 建立時間 / 操作。
- 輪替按鈕:移除「已有 2 把不可輪替」的禁用邏輯與提示,改為輪替前二次確認,文案講明「舊密鑰將立即失效」。
- 編輯 dialog:限流兩個輸入框維持分開。
- 密鑰面板(task-009 的 reveal 面板)配合單鑰制簡化:當前 active 一把 + 歷史 retired 列。

**清資料(worker 於 Acceptance 全過後、回報前執行)**:
- 對開發 DB(localhost:5435)執行:`UPDATE api_client_secrets SET is_deleted = true, updated_at = now() WHERE is_deleted = false;` 與 `UPDATE api_client_users SET is_deleted = true, updated_at = now() WHERE is_deleted = false;`(參數化 / psql 直跑皆可,**禁 DELETE / TRUNCATE / DROP**)。
- 驗證:管理 API `GET /api/v1/api-clients` 回空清單。

## Acceptance

- [ ] `uv run pytest tests/test_api_client_models_repo.py tests/test_api_clients_api.py tests/test_api_client_token_api.py` 全綠(改寫:rotate 後舊鑰立即 401、同時最多 1 把 active(rotate N 次後 active 恆 1、retired 累積)、雙鑰並存相關測試移除或改寫)
- [ ] `uv run pytest` 全套全綠;ruff + mypy 無新增錯誤
- [ ] `cd frontend && npm run lint` + `npx tsc --noEmit` + `npm run build` 三項乾淨
- [ ] 真實 API:建立使用者 → 取證成功 → rotate → 舊 secret 打 `/token` 401、新 secret 200;表格僅單一「流量上限」欄
- [ ] 開發 DB 測試資料清空:`GET /api/v1/api-clients` 回空,DB 無 `is_deleted=false` 的 api_client_users 列
- [ ] Arch 文件與 propose 變更紀錄補「單一密鑰制(發新即撤舊)取代雙鑰並存」一筆(比照 task-009 的變更紀錄寫法)

## 完成註記(orchestrator,2026-07-30)

user 於執行中追加四項 UI 裁定,一併落地:「ClientID-Secret」合併單欄(格內上行 client_id+複製、下行 secret 遮罩檢視)、移除「密鑰紀錄」按鈕與展開面板(含手動 retire UI 入口;後端 retire 端點保留)、操作欄(編輯・輪替)移至最左、副標移除「(admin 專用)」。最終表格 6 欄:操作 / 使用者 / ClientID-Secret / 狀態 / 流量上限 / 建立時間。

- 後端:`repo.add_secret` 同交易先 retire 全部 active 再插新列(單一密鑰制);MAX_ACTIVE_SECRETS 與 409 檢核移除;rotate audit 註記「舊密鑰已自動撤銷」。
- 測試:三檔雙鑰情境改寫為單鑰語意(rotate N 次 active 恆 1、retired 累積、撤銷唯一 active 後歸零可再發),52 測綠;全套 **423 passed**;ruff 乾淨;mypy 僅既存 `schedule_repo.py:528`。
- 前端:tsc / eslint(--max-warnings=0)/ build 三項乾淨;輪替改二次確認(文案講明舊鑰立即失效)。
- 真實 API(重建 backend+frontend 容器):建立(active=1)→ 舊 secret 取證 200 → rotate(active_count=1)→ **舊 secret 401 invalid_client、新 secret 200**。
- 清資料:開發 DB `api_client_secrets` 16 列、`api_client_users` 8 列全部軟刪(UPDATE is_deleted=true,無 DELETE);`GET /api/v1/api-clients` 回空清單(total=0)。
- 文件:Arch 四處「雙鑰輪替/並存」改「單一密鑰制:輪替發新即自動撤舊」;propose 變更紀錄追加一條。

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/02-frontend/00-overview.md`
