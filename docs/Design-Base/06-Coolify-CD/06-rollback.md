# 06-rollback — 回滾流程

> **何時讀**:部署出問題 / 緊急回滾才讀。

兩段:**Coolify 內建 rollback**(快)+ **緊急 git revert + push**(主流程,可重跑 CI)。

---

## 回滾判準(任一觸發)

- healthcheck 連 ≥ 3 次失敗(Coolify 自動回滾)
- 部署後 30 分鐘內 5xx 比例 > 5%
- 主要 user journey 手測無法完成(對齊 `05-deploy-flow.md § 部署後驗證`)
- 客戶回報關鍵功能掛(支援 / 業務告知)

## 路徑 A:Coolify 內建 rollback(快,首選)

Coolify Application → Deployments 頁 → 選上一版 deployment → **Redeploy this version**。

- 適用情境:image 還在(Coolify 預設保留前 N 版),且問題不在 DB schema
- 時間:< 2 分鐘(同新部署,但跑舊 image)
- **不**會回滾 DB migration(若新版有 migration,DB 仍是新 schema)

## 路徑 B:git revert + push(主流程)

```bash
# 在本機
git checkout main
git pull origin main
git revert <bad-commit-hash>          # 產生反向 commit
git push origin main
```

→ 觸發 Coolify webhook → 跑 CI → build → deploy。

- 適用情境:任何問題,**首選**(歷史可追,可走 CI 二次驗證)
- 時間:5–10 分鐘(等 CI + build)
- 適合 DB schema 已往前但 app 要回退 → 配合 `forward fix`(見下)

## 不要做

- ❌ `git push --force`(對齊 `99-code-review/02-commit-message.md` 禁強推)
- ❌ `git reset --hard <old> && git push --force`(改寫歷史,team 災難)
- ❌ 直接在跳板機改 image(失去 audit trail)
- ❌ 關 Coolify 自動 rollback(失去 healthcheck guard)

## DB schema 已往前的情境

新版若已跑 migration → app 回退 ≠ DB 回退。原則 **forward fix > 反向 migration**:

1. **首選**:寫修復 commit + push,讓 app 補相容(例:舊 code 也能讀新欄位)
2. 不可逆 / 沒辦法兼容 → 寫反向 migration(`alembic downgrade -1`)+ 評估資料風險(可能丟新欄位資料)
3. 大量資料 backfill 已執行 → 不能 revert,只能 forward fix

DB migration 規範見 `04-databases/08-alembic.md`(round-trip 驗證為前提)。

## 回滾後 follow-up

回滾完成 ≤ 24 hr 內必走:

1. 寫 `fixed.md`:根因 / 影響範圍 / 修正計畫
2. 開重新部署 task:修正版的 propose / task / Acceptance(避開原問題)
3. reflect 候選:本次 root cause 是否該升規(對齊 `01-propose/07-rule-evolution.md`)
4. 若涉資料異動 → 通報相關 stakeholder(業務 / 客戶)

## 演練

每季至少演練 1 次回滾流程:

- staging 環境跑路徑 A + 路徑 B
- 計時:目標路徑 A < 2 分、路徑 B < 10 分
- 演練紀錄寫於 `docs/Tasks/v*/fixed.md` 或專屬 SOP
