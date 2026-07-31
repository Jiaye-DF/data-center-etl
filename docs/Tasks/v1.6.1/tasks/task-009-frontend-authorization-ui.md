---
id: task-009
title: 前端授權管理 UI(系統別 / 作業範圍 / 設定檔矩陣 / Role / 特例)
status: done
parallel: false
depends_on: [task-008]
affected_files:
  - frontend/src/app/(main)/client-settings/page.tsx
  - frontend/src/lib/api/clientSettingApi.ts
estimated_hours: 4
model: opus
effort: medium
---

## 目標

完成四分頁的操作 UI,走完 Arch 後台流程 ⓪→②:建系統別 → 系統別下建作業並勾表 × 欄位範圍 → 設定檔勾作業 + 每作業授權矩陣(逐表逐欄 read/edit、`*` 全欄位)→ Role 綁定設定檔;特例組同矩陣語意 + 效期欄。

## 實作要點

- 表 / 欄位選項來源 = semantic confirmed 映射(經後端驗證,前端下拉 / 勾選僅列可授權項;缺映射顯示明確空狀態不報錯)。
- 授權矩陣 UI:作業 → 表 → 欄位 × read/edit 勾選;「`*` 全欄位」為表級快捷;整批存檔(對應後端 PUT 置換);超範圍 / 未勾作業的後端 422 / 409 錯誤逐筆顯示。
- Role 表單必選設定檔(前端擋空 + 顯示後端 422);刪除防呆 409 訊息友善呈現。
- 危險操作(刪系統別 / 作業 / 設定檔 / Role / 特例組)走既有 ConfirmDialog 二次確認;文案以「使用者」稱 API Client(沿用 v1.6.0 用詞裁定)。
- 樣式對齊 api-clients 頁(膠囊鈕 / df-card / df-table 慣例)。

## Acceptance

- [ ] `npm run lint` + `npm run typecheck` 乾淨
- [ ] `docker compose up -d --build` 後手測:依 Arch 範例建 erp → O1(三表六欄範圍)→ P1 矩陣授權 → Role 綁 P1 全程可於 UI 完成且資料落 RDS(重整頁面仍在)
- [ ] Role 表單不選設定檔無法送出;刪除被綁定資源顯示 409 訊息且清單不變

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
