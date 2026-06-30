# 06-security-checklist — 安全抽查清單

> **何時讀**:PR review 抽查安全 / 處理安全 issue 才讀。

對齊 OWASP Top 10;對應硬規則散落於 `00-overview/02-secrets.md`、`03-backend/02-auth.md`、`04-databases/03-passwords-and-pii.md`、`05-CI/04-secret-scan.md` / `05-security-scan.md`。

---

## OWASP Top 10 對應

### A01:存取控管失誤(Broken Access Control)

- [ ] 所有保護 endpoint 走 `Depends(require_role(...))` / `require_permission(...)`(`03-backend/02-auth.md`)
- [ ] **禁**前端依賴隱藏路由 / disabled 按鈕做授權(僅 UX,後端必再驗)
- [ ] 跨 user 資源(例 `/api/v1/orders/<uid>`)必驗 ownership(`order.user_uid == current_user.uid`)
- [ ] admin 操作有 audit log(誰 / 何時 / 改了什麼)

### A02:加密失誤(Cryptographic Failures)

- [ ] 機密 / token 不寫 log / response(`00-overview/02-secrets.md § Log / error 過濾`)
- [ ] 密碼用 `bcrypt`(`04-databases/03-passwords-and-pii.md`),**禁** `sha256` / 自寫 hash
- [ ] JWT 用 `HS256` 或 `RS256`(對應 `pyjwt[crypto]`),`alg: none` 拒
- [ ] DB connection / API call 必 TLS;**禁**明文(`08-domains-and-tls.md`)

### A03:Injection

- [ ] SQL:用 SQLAlchemy ORM 或 `text(...).bindparams(...)`,**禁**字串拼接 / f-string(`04-databases/04-sql-safety.md`)
- [ ] HTML:輸出 user input 必 escape(React 預設 escape;`dangerouslySetInnerHTML` 必驗 sanitizer)
- [ ] Shell:**禁** `subprocess.run(..., shell=True)` 帶 user input
- [ ] LDAP / NoSQL / 第三方 query language:同樣 parameterized

### A04:Insecure Design

- [ ] 速率限制(rate limit)— 對 `/auth/login` / `/auth/reset-password` 等敏感 endpoint 加(`90-third-party-service/02-rate-and-cost.md`)
- [ ] 業務邏輯漏洞(金額後端算、idempotency、webhook 驗簽)— 對齊 `90-third-party-service/05-payment.md`

### A05:Security Misconfiguration

- [ ] `.env` / credentials 不曾 commit(`05-CI/04-secret-scan.md`)
- [ ] `CORS_ORIGINS` 限本網域,**禁** `["*"]`(`03-backend/02-auth.md`)
- [ ] `/api/docs` production 是否該保護(`00-overview/04-api-docs.md`)
- [ ] error 回應不洩內部架構(stack trace 不回前端)
- [ ] container 非 root(`06-Coolify-CD/02-dockerfile-backend.md`)

### A06:Vulnerable & Outdated Components

- [ ] `npm audit --audit-level=high` / `pip-audit` 全綠(`05-CI/03-dependency-audit.md`)
- [ ] container scan(trivy)無 HIGH / CRITICAL 已修 CVE(`05-CI/05-security-scan.md`)
- [ ] 升版獨立 commit(`00-overview/01-versions.md`)

### A07:Identification & Authentication Failures

- [ ] 密碼策略(長度 ≥ 8,複雜度 / 禁常見密碼)— 視專案
- [ ] session JWT 帶 `httpOnly + Secure + SameSite=Lax`(`03-backend/02-auth.md`)
- [ ] 登入失敗鎖定 / 速率限制
- [ ] SSO state CSRF + PKCE 驗(`90-third-party-service/04-sso-azure-ad.md`)
- [ ] logout 後 token 失效(deny list 或 token 短期 + refresh)

### A08:Software & Data Integrity Failures

- [ ] CI / CD 不從不可信 source 拉(`05-CI/08-secrets-and-oidc.md`)
- [ ] webhook 簽章驗(`90-third-party-service/05-payment.md`)
- [ ] 自動更新 / image pull 走可信 registry

### A09:Security Logging & Monitoring Failures

- [ ] 結構化 log(`03-backend/05-exceptions-and-logging.md`)
- [ ] 機密過濾(`00-overview/02-secrets.md`)
- [ ] error rate alert(`06-Coolify-CD/07-observability.md`)
- [ ] 失敗登入 / 提權操作有 audit log

### A10:SSRF

- [ ] 不接受 user 提供的 URL 直接 fetch(若必要 → 走 allowlist)
- [ ] 第三方 client 限定 base URL(對齊 `90-third-party-service/01-client-design.md`)

---

## 機密外洩抽查

- [ ] gitleaks PR 綠(`05-CI/04-secret-scan.md`)
- [ ] log / error / stack trace 不含 token / password / cookie 完整值
- [ ] 第三方錯誤訊息不直接回前端(可能洩內部 endpoint / version)

## 依賴 CVE

- [ ] `npm audit` / `pip-audit` 高危 = 0
- [ ] trivy container scan 高危 = 0
- [ ] 上游無 fix → 寫 `fixed.md` + ignore 並設重檢日期

---

## reviewer 動作

審查發現高危 → **block** PR + open issue + 寫 `fixed.md`。中危 → comment + 評估後續處理。低危 → 提建議,不擋。

任何 catch all 異常需 `--no-verify` 才能繞過 → reviewer 必擋(對齊 `99-code-review/02-commit-message.md` 禁 `--no-verify`)。
