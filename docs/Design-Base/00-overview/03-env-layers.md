# 03-env-layers — 環境分層(localhost vs 部署)

> **何時讀**:deploy / 配置 env 時讀。本檔定義**跨棧層級劃分**;部署平台(Coolify)實作見 `06-Coolify-CD/04-env-and-secrets.md`,前端 env 前綴見 `02-frontend/03-env-and-auth.md`。

---

## 三層必有

至少 **development / staging / production** 三層;各自:

- 一份 `.env.<env>.example`(可 commit,placeholder)
- 一份 `.env.<env>`(本機 / 部署平台,**禁** commit)
- frontend / backend 為**獨立 service**,各自有 `.env*.example`(前後端透過 HTTP 通訊)

## `APP_ENV` 變數(必有)

後端必讀環境變數 `APP_ENV`,值**限定** `development` / `staging` / `production`:

- 為 `Settings` 欄位,作為 fail-fast 判斷依據(見 `03-backend/04-config.md`)
- **禁**用其他值(`dev` / `prod` / `local` / `test` 等簡寫);**禁**省略
- 前端不需 `APP_ENV`(用 build mode + `NEXT_PUBLIC_*` / `VITE_*` 區分)

## 載入優先序(後端)

`process env` > `.env.<APP_ENV>` > 預設值。例:`APP_ENV=development` → 載 `.env.development`。CI / 部署平台**直接**注入 process env,**禁**放 `.env` 檔到容器內(見 `06-Coolify-CD/04-env-and-secrets.md`)。

## 各層差異(典範)

| | development | staging | production |
| --- | --- | --- | --- |
| `.env` 檔 | `.env.development`(從 example) | `.env.staging` | `.env.production` |
| `APP_ENV` | `development` | `staging` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://...@localhost:5432/...` | `...@<staging-host>:5432/...`(**獨立** DB)| `...@<production-host>:5432/...` |
| `JWT_SECRET_KEY` | development 預設值(可) | **必**改 32+ 字元隨機 | **必**改 32+ 字元隨機 |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | `["https://staging.<domain>"]` | `["https://<domain>"]`(**禁** `["*"]`) |
| 第三方 | mock / sandbox | sandbox | live(以 staging 驗收後切) |
| log level | `DEBUG` | `INFO` | `INFO` / `WARNING` |
| `/api/docs` | 開 | 開 | 視專案(見 `04-api-docs.md`) |

## development = localhost

- 後端 dev server + 前端 dev server;依賴服務由開發者於本機 install(`docker compose -f docker-compose.development.yml up postgres`)
- 連線指向 `localhost:*`
- 機密為 development 預設值;`.env.development.example` 可直接複製為 `.env.development` 跑通

## staging vs production

- staging = production 同形態(image / compose / Dockerfile 一致)+ **獨立** DB / 機密 + sandbox 第三方
- staging 用於部署流程驗收,**禁**接 production DB / live 第三方
- production = 對外服務,所有規則最嚴

## 禁混用

- **禁**把 `.env.development` 拿去部署 — 連不到 DB(localhost 不存在於遠端)+ 機密為 development 預設值會觸發 fail-fast
- **禁**讓 staging / production 共用同一 DB / 同一 secret

## 部署前 checklist

- [ ] `APP_ENV` 設為 `staging` 或 `production`(**禁** `development`,**禁**簡寫如 `dev` / `prod`)
- [ ] 所有 `localhost:*` 已換真實 host
- [ ] 機密均為**獨立**生成(`openssl rand -base64 32` 或同等強度),非 development 預設
- [ ] `CORS_ORIGINS` 限本網域(**禁** `["*"]`)
- [ ] log level 非 `DEBUG`
- [ ] `.env.<env>.example` 與 `.env.<env>` 欄位一致(無遺漏 / 無多餘)
