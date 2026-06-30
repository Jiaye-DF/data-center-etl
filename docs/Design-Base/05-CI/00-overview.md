# 00-overview — CI 入口

> **何時讀**:任何 CI workflow 任務都讀;具體 job 細節依任務載入對應子檔。

GitHub Actions 為唯一 CI(企業現況);workflow 走 `.github/workflows/*.yml`。

---

## Workflow 結構(永遠遵守)

```
.github/workflows/
├── ci.yml             # 主 workflow:lint + typecheck + test + audit + scan
├── e2e.yml            # Playwright(預設 if: false,見 06-e2e.md)
└── deploy.yml         # 由 06-Coolify-CD 觸發,本資料夾不負責
```

`ci.yml` 必含 jobs:
- `frontend-test`(npm ci → lint → typecheck → test → build)— 細節見 `01-frontend-jobs.md`
- `backend-test`(uv sync → ruff → mypy → pytest → alembic round-trip)— 細節見 `02-backend-jobs.md`
- `dependency-audit`(npm audit / pip-audit)— 見 `03-dependency-audit.md`
- `secret-scan`(gitleaks)— 見 `04-secret-scan.md`
- `security-scan`(semgrep / trivy)— 見 `05-security-scan.md`

## 觸發策略(永遠遵守)

```yaml
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
```

- `push` 到 `main` → 跑 ci(部署觸發走 Coolify webhook,**不**在這裡)
- 開 / 更新 PR → 跑 ci
- **禁** `on: workflow_dispatch` 為唯一觸發(漏跑風險)
- **禁**為了避開 CI 用 `[skip ci]`(規則為地板)

## Job 命名與並行

- job 名一律 kebab-case(`frontend-test` / `backend-test`)
- 獨立 area 必並行(`frontend-test` / `backend-test` / `dependency-audit` 同層)
- 有依賴用 `needs:`(例:`build` 需要 `lint` + `test`)

## 容忍度(統一原則)

- lint / typecheck / test → **必綠**(failure → block PR)
- dependency audit → 過渡期 `continue-on-error: true`,有時程改 `false`(見 `03-dependency-audit.md`)
- e2e → 預設 `if: false`(見 `06-e2e.md`)
- 對 lint warning **不**容忍(visible warning 視為 failure)— 見 `99-code-review/04-lint-checklist.md`

---

## 子章節

- `01-frontend-jobs.md` — 前端 jobs 細節
- `02-backend-jobs.md` — 後端 jobs 細節
- `03-dependency-audit.md` — npm audit / pip-audit
- `04-secret-scan.md` — gitleaks / trufflehog
- `05-security-scan.md` — semgrep / trivy
- `06-e2e.md` — Playwright
- `07-branch-protection.md` — `main` 保護規則
- `08-secrets-and-oidc.md` — GitHub Secrets / OIDC
