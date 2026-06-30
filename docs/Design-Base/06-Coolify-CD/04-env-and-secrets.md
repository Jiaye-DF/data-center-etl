# 04-env-and-secrets — Coolify env 注入 + 機密

> **何時讀**:在 Coolify 設定 env / rotate 機密才讀。對應規則見 `00-overview/02-secrets.md` / `03-env-layers.md`。

---

## Coolify env 注入機制

Coolify Application 設定頁 → **Environment Variables** 頁籤,兩種注入方式:

| 種類 | 用途 | 容器內表現 | 何時用 |
| --- | --- | --- | --- |
| **Build-time** | 進入 build process(`ARG` / `ENV` 在 builder stage) | image build 時讀;**烙印**進 image | 前端 `VITE_*` / `NEXT_PUBLIC_*`(編譯進 bundle) |
| **Runtime** | 容器啟動時注入 process env | runtime 讀;**不**烙印 | 後端機密 / DB URL / JWT secret |

**規則**:

- 機密(token / password / connection string)**僅**走 runtime,**禁** build-time
- 前端 `*_PUBLIC_*` / `VITE_*` 視為公開資料(會進 bundle),**禁**帶機密
- 同一 env 名**禁**同時設 build-time + runtime(優先序模糊,踩雷)

## Coolify Secrets vs 環境變數

Coolify 區分:

- **Environment Variables**:明文存 Coolify DB(operator 可讀)
- **Secrets**(若 Coolify 版本支援):加密存,operator UI 不可讀

對齊 `00-overview/02-secrets.md § 機密類別`:

- 真正的機密(JWT_SECRET / DB password / API key)→ **Secrets** 欄
- 非機密配置(`APP_ENV` / `CORS_ORIGINS` / `LOG_LEVEL`)→ Environment Variables

若 Coolify 版本未分:全走 Environment Variables 但**限制 admin 讀取權**(走 RBAC)。

## env 來源優先序

```
Coolify Runtime Env  >  image 內 ENV  >  app code 預設
```

`docker-compose.yml` 的 `environment:` 區塊用 `${VAR}` 引用 Coolify 注入的值;**禁**直寫 secret。

## 部署前 env checklist

新環境(staging / production)第一次部署前,Coolify env 頁必設(對齊 `00-overview/03-env-layers.md`):

- [ ] `APP_ENV=staging` 或 `production`(對齊 `00-overview/03-env-layers.md`,**禁**簡寫)
- [ ] `DATABASE_URL`(指向真實 host)
- [ ] `JWT_SECRET_KEY`(32+ 字元隨機,**禁** development 預設值)
- [ ] `CORS_ORIGINS`(限本網域,**禁** `["*"]`)
- [ ] `POSTGRES_VERSION` / 其他 `*_VERSION`(對齊 `00-overview/01-versions.md`)
- [ ] 第三方 API key(SMTP / Stripe / Azure AD,對齊 `90-third-party-service/`)
- [ ] `TZ=Asia/Taipei`(若 image 沒設好)

## 機密 rotation

走 `00-overview/02-secrets.md § 外洩 incident 流程`,Coolify 操作步驟:

1. Coolify env 頁改新值
2. 觸發 redeploy(env 變更不會自動重啟,**必**手動或設 webhook)
3. 確認新 container healthy 後,於第三方 provider 撤銷舊 key
4. 寫 `fixed.md`:時間 / 影響範圍 / 修正

## env 同步檢查

`.env.<env>.example`(repo 內 placeholder)與 Coolify env 頁的欄位**必一致**:

- 新增 secret 欄位 → 同步:`.env*.example`(全層)+ `Settings` 欄位 + Coolify env 頁
- 缺欄 → app fail-fast(對齊 `03-backend/04-config.md`)

## 不要做

- ❌ 把 `.env.<env>` 檔放進 git / image
- ❌ Coolify env 設 `***` / `xxx` 等假值(`Settings` fail-fast 會擋)
- ❌ build-time env 帶機密
- ❌ 同一 secret 多環境共用(staging 與 production 必獨立生成)
