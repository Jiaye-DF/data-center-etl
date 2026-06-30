# 02-secrets — 敏感資訊

> **何時讀**:處理 env / auth / log 時讀。本檔定義**跨棧通用**的機密處理底線;具體 fail-fast 實作見 `03-backend/04-config.md`,CI 掃描見 `05-CI/04-secret-scan.md`,部署平台注入見 `06-Coolify-CD/04-env-and-secrets.md`。

---

## 機密類別(必走 env)

下列任一視為機密,**禁**字面值寫入程式碼 / config 檔 / Dockerfile:

- 認證 secret:JWT secret / cookie session secret / OAuth `client_secret`
- 帳密:DB / SMTP / Basic auth password
- API key / token / webhook secret
- Private key:`*.key` / `*.pem` / SSH key
- Connection string(內含密碼者)

機密**僅**透過 env(`Settings(BaseSettings)` 讀取),禁從程式碼字面值或 hard-coded 預設值。

## env 命名

- `SCREAMING_SNAKE_CASE`
- 結構 `<DOMAIN>_<KIND>`,例:`JWT_SECRET_KEY` / `SMTP_PASSWORD` / `STRIPE_API_KEY` / `AZURE_AD_CLIENT_SECRET`
- 客戶端 env(`NEXT_PUBLIC_*` / `VITE_*`)**禁**帶機密(編譯後進 bundle 公開可見);細節見 `02-frontend/03-env-and-auth.md`

## `.gitignore` 必排

```
.env
.env.development
.env.staging
.env.production
credentials*
*.key
*.pem
```

`.env.*.example`(placeholder 值)**可** commit,作為各層欄位清單。

## `.env*.example` 規則

- 每層 `.env.<env>` 必對應一份 `.env.<env>.example`
- 值一律 placeholder:`<change-me>` / `development-only-not-for-production` / 空字串,**禁**真實機密
- 新增 secret 欄位 → 同步:`.env*.example`(全層)+ `Settings` 欄位 + `Settings` fail-fast validator 清單
- 缺欄視為 bug

## 機密**不可**曾 commit

- `git log --all -- .env .env.development .env.staging .env.production` 須為空(`.env.*.example` 除外)
- 若曾 commit → **全 key rotate** + 用 `git filter-repo` 清史
- 主動掃描工具(gitleaks / trufflehog)見 `05-CI/04-secret-scan.md`

## Log / error 過濾

- **禁** log:token、password、cookie 完整值、完整 connection string、private key
- 必要時遮罩:`****` 或 hash 前 8 碼(`hashlib.sha256(...).hexdigest()[:8]`)
- exception trace 印 args / locals 須先過濾(避免 secret 透過 stack trace 外洩);結構化 log 規範見 `03-backend/05-exceptions-and-logging.md`

## 外洩 incident 流程

發現機密外洩(commit history / log / 截圖 / 第三方告知 / `gitleaks` 命中):

1. **立即 rotate** 所有環境的該 secret(development / staging / production 同步)
2. **撤銷舊值**:JWT 列入 deny list、API key 從 provider revoke、DB 帳密改密碼
3. 寫 `docs/Tasks/v*/fixed.md`:外洩源 / 影響範圍 / 修復步驟 / 後續防護
4. 補 `05-CI/04-secret-scan.md` 規則或 pre-commit hook 防再犯

## 啟動 fail-fast

`APP_ENV=staging` / `production` 帶 development 預設值 → 啟動 raise;實作見 `03-backend/04-config.md § 啟動 fail-fast`。新 secret 加欄位時**同步**加進 fail-fast validator 清單。
