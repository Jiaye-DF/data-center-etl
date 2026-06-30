# 08-secrets-and-oidc — GitHub Secrets / OIDC

> **何時讀**:CI 需要機密(部署 token / 第三方 sandbox key)才讀。對應規則見 `00-overview/02-secrets.md`。

---

## GitHub Secrets

機密注入 ci 走 `secrets.<NAME>`:

```yaml
env:
  STRIPE_SANDBOX_KEY: ${{ secrets.STRIPE_SANDBOX_KEY }}
```

設定位置(管理權限 limited):

- Repo:Settings → Secrets and variables → Actions
- Org:Settings → Secrets and variables → Actions(跨 repo 共用)

### 規則

- 命名同 `00-overview/02-secrets.md § env 命名`(SCREAMING_SNAKE)
- **禁**明文寫進 workflow yml(對齊 `00-overview/02-secrets.md`)
- **禁**把 secret echo / print(GitHub 自動遮罩,但行為仍記錄,屬 anti-pattern)
- 環境分層:用 GitHub Environments(`staging` / `production`)各自綁 secret 集合,workflow 走 `environment: production` 才取
- secret rotate → 同步走 `00-overview/02-secrets.md § 外洩 incident 流程`

## OIDC(雲端短期 token)

部署到 AWS / GCP 時**禁**長期靜態 IAM key,走 GitHub OIDC 換短期 token:

```yaml
permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::<acct>:role/<role>
          aws-region: ap-northeast-1
```

雲端 IAM trust policy 必綁 GitHub OIDC issuer + 限定 repo / branch / environment。

> 本企業現況**主走 Coolify**(自架),OIDC 對應較少;若有 AWS / GCP serverless(GCP Cloud Run / AWS Lambda)才需 OIDC。

## Coolify 部署 token

Coolify webhook 觸發部署不在本 ci 範圍,走 Coolify 自身機制(見 `06-Coolify-CD/05-deploy-flow.md`)。CI 不負責 push image 到 Coolify;Coolify 自拉 git。

## 第三方 sandbox key

- 只放 sandbox / test key(對齊 `00-overview/03-env-layers.md § 各層差異`)
- **禁**把 production key 放 GitHub Secrets 給 ci 用
- production key 只在部署平台(Coolify)注入,ci 不接觸

## 機密 rotate 時程

- secret 引入 / rotate → 登記於 `docs/Tasks/v*/fixed.md` 或專屬 SOP
- 預設 rotate 週期:**90 天**(JWT signing key / API key)
- 緊急 rotate 24 hr 內完成所有環境同步
