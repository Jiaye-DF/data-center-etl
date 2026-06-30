# 07-branch-protection — `main` 保護規則

> **何時讀**:設定 GitHub branch protection / 改保護規則才讀。

`main` 為唯一 protected branch(企業現況 — 主分支唯一)。

---

## 必設規則(GitHub Settings → Branches → main)

| 項目 | 設定 | 理由 |
| --- | --- | --- |
| **Require a pull request before merging** | ✅ ON | 禁直接 push to main |
| **Require approvals** | ≥ 1 | reviewer 同意 |
| **Dismiss stale pull request approvals when new commits are pushed** | ✅ ON | 重大改動需重審 |
| **Require status checks to pass before merging** | ✅ ON + 列 ci 必綠 | 對齊 `00-overview.md § Workflow 結構` |
| **Require branches to be up to date before merging** | ✅ ON | 避免 base branch CI 過期 |
| **Require conversation resolution before merging** | ✅ ON | review comment 須處理完 |
| **Require linear history** | ✅ ON | 禁 merge commit;PR 一律 squash |
| **Do not allow bypassing the above settings** | ✅ ON | admin 也禁繞過 |
| **Allow force pushes** | ❌ OFF | 對齊 `99-code-review/02-commit-message.md § 禁 force push` |
| **Allow deletions** | ❌ OFF | 禁刪 main |

## Required status checks

加入 ci.yml 所有 jobs(對齊 `00-overview.md`):

- `frontend-test`
- `backend-test`
- `dependency-audit`(`continue-on-error: false` 後加入)
- `secret-scan`(永遠 required)
- `security-scan`
- `e2e`(啟用後加入,見 `06-e2e.md`)

## reviewer 數量

- 預設 ≥ 1
- 跨 area 高風險 PR(改 `00-overview/*` / `99-code-review/*`)→ ≥ 2(由 PR template 提示)

## CODEOWNERS

設 `.github/CODEOWNERS` 指定各 area 主負責:

```
docs/Design-Base/00-overview/   @<lead>
docs/Design-Base/02-frontend/   @<frontend-lead>
docs/Design-Base/03-backend/    @<backend-lead>
docs/Design-Base/04-databases/  @<db-lead>
docs/Design-Base/06-Coolify-CD/ @<devops-lead>
.github/workflows/              @<devops-lead>
```

## 例外處理

緊急 hotfix 須繞過審查 → **不**允許關掉保護規則;改走:
1. owner 直接 review + approve(走 PR 流程,但加速)
2. 或啟用 GitHub `auto-merge`(等 ci 綠 + 1 approval 自動 merge)

**禁**為了快關保護;一旦關過很容易忘記重啟 → 寫 `fixed.md` 記錄。
