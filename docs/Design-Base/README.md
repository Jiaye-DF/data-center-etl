# Design-Base — 索引(任務 → 檔案 對照表)

> **本檔目的**:任何 agent 進入任務時**先讀本檔**,即可知道要載入哪些規範,**不必**全資料夾掃描。
>
> **更新原則**:新增 / 棄用任一規範檔 → **同步**更新本檔(否則 agent 會漏載)。本檔與 `Harness-Engineering/AGENTS.md § Just-in-time Loading` 必一致。

---

## 永遠載入(任何任務)

任何任務都**必**載入下列檔(底線):

- `Harness-Engineering/AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md` — 規範優先序 + 輸出語言
- `docs/Design-Base/02-frontend/00-overview.md` — 前端風格地板(若任務涉及前端)
- `docs/Design-Base/03-backend/00-overview.md` — 後端風格地板(若任務涉及後端)
- `docs/Design-Base/04-databases/00-overview.md` — DB 風格地板(若任務涉及 DB)
- `docs/Design-Base/90-third-party-service/00-overview.md` — 治理底線(若任務涉及第三方)
- `docs/Design-Base/99-code-review/00-overview.md` — Acceptance gate(發 PR 前)

---

## 任務 → 必讀檔 對照表

> 以**該任務情境**找列;「+」表示在「永遠載入」之外**追加**載入。

### 跨領域 / 配置

| 任務 | 必讀檔(追加) |
| --- | --- |
| 加套件 / 升版 | `00-overview/01-versions.md` |
| 改 env / secret / `.env*` | `00-overview/02-secrets.md` + `00-overview/03-env-layers.md` |
| 部署 / 配 staging or production env | `00-overview/03-env-layers.md` + `06-Coolify-CD/04-env-and-secrets.md` |
| 寫 FastAPI 入口 / 改 docs URL | `00-overview/04-api-docs.md` |
| 任何時間 / 日期欄位 | `00-overview/05-timezone.md` + 對應 area 檔 |

### Propose / Tasks / Multi-agent

| 任務 | 必讀檔(追加) |
| --- | --- |
| 啟動新版本 / 寫 propose | `01-propose/00-overview.md` + `01-propose/01-propose-format.md` + `01-propose/05-version-bump.md` |
| Orchestrator 拆 tasks | + `01-propose/02-task-decomposition.md` |
| Multi-agent 並行執行 | + `01-propose/03-multi-agent-flow.md` |
| 寫 fixed.md | `01-propose/04-fixed-format.md` + `99-code-review/01-fixed-md.md` |
| 寫 CHANGELOG.md(release 前) | `01-propose/06-changelog.md` |
| 跑 `/reflect-rules` / 升規 | `01-propose/07-rule-evolution.md` |

### Frontend

| 任務 | 必讀檔(追加) |
| --- | --- |
| **任何前端任務** | `02-frontend/00-overview.md`(永遠讀) |
| 寫 app 結構 / 頁面 / 全域錯誤邊界 | + `02-frontend/01-routing-and-error.md` |
| Data fetching / 狀態管理 | + `02-frontend/02-api-and-state.md` |
| client config / 登入 / SSO | + `02-frontend/03-env-and-auth.md` + `90-third-party-service/04-sso-azure-ad.md`(若 SSO) |
| 日期時間顯示 | + `02-frontend/04-datetime.md` + `00-overview/05-timezone.md` |
| Dialog / 共用 Hook / 任何 reuse(component / hook / utility) | + `02-frontend/05-components.md` |
| RWD / 樣式 / 版面 / 觸控目標 | + `02-frontend/06-rwd.md` |

### Backend

| 任務 | 必讀檔(追加) |
| --- | --- |
| **任何後端任務** | `03-backend/00-overview.md`(永遠讀) |
| 寫新 API endpoint | + `03-backend/01-routing.md` |
| 寫保護 endpoint / 登入 / CORS | + `03-backend/02-auth.md` |
| Service 跨表 / hash / 阻塞操作 | + `03-backend/03-async-and-tx.md` |
| 改 config / 啟動 flow | + `03-backend/04-config.md` + `00-overview/02-secrets.md` |
| 加 log / 處理錯誤 | + `03-backend/05-exceptions-and-logging.md` |
| 串第三方 | + `03-backend/06-clients.md` + `90-third-party-service/01-client-design.md` |
| 寫後端測試 | + `03-backend/07-testing.md` |
| 後端效能 / N+1 / async 阻塞 | + `03-backend/08-performance.md` |

### Database

| 任務 | 必讀檔(追加) |
| --- | --- |
| **任何 DB 任務** | `04-databases/00-overview.md`(永遠讀) |
| 設計新表 | + `04-databases/01-identifiers.md` |
| 寫 Repository | + `04-databases/02-soft-delete.md` |
| 處理使用者資料 / PII / 密碼 | + `04-databases/03-passwords-and-pii.md` |
| 寫 raw SQL | + `04-databases/04-sql-safety.md` |
| 金額 / 計費欄位 | + `04-databases/05-precision.md` |
| 時間欄位 | + `04-databases/06-timezone.md` + `00-overview/05-timezone.md` |
| 改連線設定 / 連線池 | + `04-databases/07-connection.md` |
| 寫 / 改 migration | + `04-databases/08-alembic.md` |
| 優化 query / 索引 | + `04-databases/09-indexes-and-perf.md` |
| 評估要不要加請求 log / register middleware | + `04-databases/10-statistics-log.md`(選用,需 Redis) |

### CI

| 任務 | 必讀檔(追加) |
| --- | --- |
| **任何 CI workflow 任務** | `05-CI/00-overview.md` |
| 改前端 ci jobs | + `05-CI/01-frontend-jobs.md` |
| 改後端 ci jobs | + `05-CI/02-backend-jobs.md` |
| 改 dependency audit | + `05-CI/03-dependency-audit.md` |
| 改機密掃描(gitleaks) | + `05-CI/04-secret-scan.md` |
| 改 SAST / container scan | + `05-CI/05-security-scan.md` |
| 啟用 / 改 e2e(Playwright) | + `05-CI/06-e2e.md` |
| 設 branch protection | + `05-CI/07-branch-protection.md` |
| 加 GitHub Secrets / OIDC | + `05-CI/08-secrets-and-oidc.md` |

### Coolify CD

| 任務 | 必讀檔(追加) |
| --- | --- |
| **任何部署任務** | `06-Coolify-CD/00-overview.md` |
| 寫 / 改 docker-compose.yml | + `06-Coolify-CD/01-compose.md` |
| 寫 / 改 backend Dockerfile | + `06-Coolify-CD/02-dockerfile-backend.md` |
| 寫 / 改 frontend Dockerfile | + `06-Coolify-CD/03-dockerfile-frontend.md` |
| Coolify env 設定 / rotate 機密 | + `06-Coolify-CD/04-env-and-secrets.md` + `00-overview/02-secrets.md` |
| 改部署觸發 / 分支策略 | + `06-Coolify-CD/05-deploy-flow.md` |
| 處理回滾 / 緊急 hotfix | + `06-Coolify-CD/06-rollback.md` |
| 接 Sentry / log / metric | + `06-Coolify-CD/07-observability.md` + `90-third-party-service/06-monitoring.md` |
| 綁 domain / TLS / preview env | + `06-Coolify-CD/08-domains-and-tls.md` |

### 第三方服務

| 任務 | 必讀檔(追加) |
| --- | --- |
| **任何串第三方** | `90-third-party-service/00-overview.md` + `01-client-design.md`(永遠讀) |
| Rate limit / API cost | + `90-third-party-service/02-rate-and-cost.md` |
| 串 SMTP / 寄信 | + `90-third-party-service/03-smtp.md` |
| 直連 Azure AD SSO(App 自當 OAuth client) | + `90-third-party-service/04-sso-azure-ad.md` |
| 串公司 DF-SSO 中央登入器 | + `90-third-party-service/08-df-sso.md`(實際落檔走 `sso-init` skill) |
| 串 Stripe / 綠界(payment) | + `90-third-party-service/05-payment.md` |
| 接 Sentry / Datadog / Loki | + `90-third-party-service/06-monitoring.md` |
| 接 reviewdog / codecov | + `90-third-party-service/07-lint-bot.md` |

### Code Review 收口

| 任務 | 必讀檔(追加) |
| --- | --- |
| 發 PR / 收口 | `99-code-review/00-overview.md` + `99-code-review/03-pr-self-check.md` |
| 寫 fixed.md | + `99-code-review/01-fixed-md.md` + `01-propose/04-fixed-format.md` |
| 寫 commit message | + `99-code-review/02-commit-message.md` |
| Lint 抽查 | + `99-code-review/04-lint-checklist.md` |
| 效能抽查 | + `99-code-review/05-performance-checklist.md` |
| 安全抽查 | + `99-code-review/06-security-checklist.md` |
| Review 流程 / 衝突仲裁 | + `99-code-review/07-review-process.md` |

---

## 檔案 → 用途 索引

### `00-overview/` — 跨領域共通底線

| 檔 | 用途 |
| --- | --- |
| `00-overview.md` | 入口 + 規範優先序 + 輸出語言 + commit |
| `01-versions.md` | 版本鎖到 patch + 套件清單 + 強制鎖定 React 19.2 / Python 3.14 |
| `02-secrets.md` | 機密 env 注入 + `.gitignore` + log 過濾 + 外洩 incident |
| `03-env-layers.md` | development / staging / production 三層 + APP_ENV + 部署前 checklist |
| `04-api-docs.md` | `/api/docs` 路徑 + OpenAPI metadata 必填 + 環境暴露 |
| `05-timezone.md` | 全棧 UTC+8 / Asia/Taipei + container TZ + Bash 取時 |

### `01-propose/` — 版本工作流

| 檔 | 用途 |
| --- | --- |
| `00-overview.md` | propose / tasks / fixed / changelog 關係 + multi-agent flow |
| `01-propose-format.md` | User 寫 propose-vX.Y.Z.md 格式 |
| `02-task-decomposition.md` | Orchestrator 拆 tasks 方法論(粒度 / 依賴 / 並行) |
| `03-multi-agent-flow.md` | Orchestrator-Workers 協議 + 衝突解決 + 進度同步 |
| `04-fixed-format.md` | fixed.md 條目格式(根因為核心) |
| `05-version-bump.md` | major / minor / patch 判準 + 3-digit semver |
| `06-changelog.md` | 對外 user-facing CHANGELOG 格式 |
| `07-rule-evolution.md` | fixed → reflect → docs/Design-Base 升級閉環 |

### `02-frontend/` — React + TypeScript

| 檔 | 用途 |
| --- | --- |
| `00-overview.md` | 風格地板:TS strict / 渲染效能 / i18n / ID 隱藏 / 字級 / 命名(永遠讀) |
| `01-routing-and-error.md` | 路由錯誤邊界(`error.tsx` / `errorElement` / `global-error`) |
| `02-api-and-state.md` | API 集中(RTK Query)+ 狀態三層 |
| `03-env-and-auth.md` | env 前綴 + httpOnly cookie + SSO state CSRF |
| `04-datetime.md` | 日期顯示(統一 `utils/datetime.ts`) |
| `05-components.md` | 共用 Hook / Component / Utility(任何 reuse 必抽) |
| `06-rwd.md` | RWD:Mobile-first + Tailwind v4 breakpoints + 觸控目標 + container queries |

### `03-backend/` — FastAPI + SQLAlchemy 2 async

| 檔 | 用途 |
| --- | --- |
| `00-overview.md` | 風格地板:分層 / 命名 / 型別 / 註解(永遠讀) |
| `01-routing.md` | 路由 + ApiResponse 外殼 + Pydantic schema |
| `02-auth.md` | JWT cookie + Depends + CORS |
| `03-async-and-tx.md` | async safety + 多表 transaction |
| `04-config.md` | Settings + fail-fast + lifespan |
| `05-exceptions-and-logging.md` | 3 個 handler + 結構化 log + 機密過濾 |
| `06-clients.md` | clients/* 結構 + httpx + 錯誤轉 AppError |
| `07-testing.md` | 真 DB 整合 + respx |
| `08-performance.md` | N+1 / async 阻塞 / 連線池 / event loop 飢餓 |

### `04-databases/` — PostgreSQL + asyncpg

| 檔 | 用途 |
| --- | --- |
| `00-overview.md` | 必備欄位 + BaseModel + SQLAlchemy 風格 + 軟刪除(永遠讀) |
| `01-identifiers.md` | pid 內部 / uid 對外 / 外部系統 ID |
| `02-soft-delete.md` | `is_deleted` + Repository 命名強制 |
| `03-passwords-and-pii.md` | bcrypt + asyncio.to_thread + PII 隔離 |
| `04-sql-safety.md` | 禁字串拼接 + `text(...).bindparams(...)` |
| `05-precision.md` | 金額 `Numeric(18, 2)` |
| `06-timezone.md` | TIMESTAMP 與顯示層全棧一致 |
| `07-connection.md` | async_sessionmaker + 連線池 |
| `08-alembic.md` | migration 命名 + round-trip |
| `09-indexes-and-perf.md` | 外鍵 / 高頻欄位 / partial index / EXPLAIN ANALYZE |
| `10-statistics-log.md` | `<project>_statistics_log` 請求 log(**選用**,需 Redis;走共用套件) |

### `05-CI/` — GitHub Actions

| 檔 | 用途 |
| --- | --- |
| `00-overview.md` | workflow 結構 + 觸發策略 + 容忍度 |
| `01-frontend-jobs.md` | npm ci / lint / typecheck / test / build |
| `02-backend-jobs.md` | uv sync --frozen / ruff / mypy / pytest / alembic round-trip |
| `03-dependency-audit.md` | npm audit / pip-audit + continue-on-error 退場 |
| `04-secret-scan.md` | gitleaks 配置 + 命中流程 |
| `05-security-scan.md` | semgrep(SAST) + trivy(container) |
| `06-e2e.md` | Playwright(預設 disabled) |
| `07-branch-protection.md` | main 必經 PR + required reviewers + 禁 force push |
| `08-secrets-and-oidc.md` | GitHub Secrets / OIDC + 雲端短期 token |

### `06-Coolify-CD/` — Coolify + Docker Compose

| 檔 | 用途 |
| --- | --- |
| `00-overview.md` | Coolify 部署模型 + 服務組成 + healthcheck |
| `01-compose.md` | docker-compose.yml 模板 + 鎖版 + healthcheck |
| `02-dockerfile-backend.md` | multi-stage / uv / 非 root / TZ |
| `03-dockerfile-frontend.md` | Vite=nginx / Next=standalone |
| `04-env-and-secrets.md` | Coolify env 注入 + Secrets vs 環境變數 + rotation |
| `05-deploy-flow.md` | git push → webhook → build → deploy + 分支策略 |
| `06-rollback.md` | Coolify rollback + git revert + DB schema 處理 |
| `07-observability.md` | log / metric / Sentry + healthcheck endpoint |
| `08-domains-and-tls.md` | Caddy / Traefik 自動 TLS + cookie domain |

### `90-third-party-service/` — 第三方串接

| 檔 | 用途 |
| --- | --- |
| `00-overview.md` | 集中位置 + 命名 + 錯誤轉換契約(永遠讀) |
| `01-client-design.md` | clients 結構 + httpx + timeout / retry / circuit breaker |
| `02-rate-and-cost.md` | client 端 throttle + cost log + 預警 |
| `03-smtp.md` | aiosmtplib + transactional vs marketing |
| `04-sso-azure-ad.md` | 直連 Azure AD:OAuth + PKCE + state CSRF + claims mapping |
| `05-payment.md` | Stripe / 綠界 + idempotency + webhook 簽章驗 |
| `06-monitoring.md` | Sentry / Datadog / Loki + PII 過濾 |
| `07-lint-bot.md` | reviewdog / codecov |
| `08-df-sso.md` | 串公司 DF-SSO 中央:4 硬性契約 + 5 端點 + 模式 A/B + silent re-auth(skill 隨附 `INTEGRATION.md` 的宣告式子集) |

### `99-code-review/` — Code Review 收口

| 檔 | 用途 |
| --- | --- |
| `00-overview.md` | Acceptance gate + 流程位置 |
| `01-fixed-md.md` | fixed.md 寫入時機 / 條目格式 / 雙向引用 |
| `02-commit-message.md` | (AI?) 類型: 描述 + 禁 force / no-verify |
| `03-pr-self-check.md` | PR self-check 列表 |
| `04-lint-checklist.md` | 各 area lint 工具 + 容忍度(零 warning) |
| `05-performance-checklist.md` | N+1 / re-render / 大 JSON / DB plan |
| `06-security-checklist.md` | OWASP Top 10 + 機密 + dependency CVE |
| `07-review-process.md` | 流程 + 誰 review + 衝突仲裁 |

---

## 維護準則

1. **新增規範檔** → 同步加進「任務 → 必讀檔」+「檔案 → 用途」兩節
2. **棄用規範檔** → 該檔頭加 `> 狀態:已棄用,見 fixed.md vX.Y.Z §N`,本檔對應條目加 `~~刪線~~`(不直接移除,留歷史)
3. **本檔與 `Harness-Engineering/AGENTS.md § Just-in-time Loading`**:同源,任一更新另一同步
4. 任何 PR 改動 `docs/Design-Base/*` 結構 → reviewer 必檢查本檔是否同步
