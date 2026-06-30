# 05-deploy-flow — 部署流程

> **何時讀**:設定 Coolify webhook / 改部署觸發策略才讀。

`git push` → GitHub webhook → Coolify build → deploy 的端到端流程。

---

## 分支策略

| Branch | 環境 | 部署觸發 |
| --- | --- | --- |
| `main` | **production** | push to `main` → Coolify production app 自動部署 |
| `staging` | **staging** | push to `staging` → Coolify staging app 自動部署 |
| feature 分支 | development / preview(可選) | 不自動部署;走 PR + 本地 development |

- **禁**從 feature 分支直接部署 production(必走 PR → main)
- **禁**讓 staging 與 production 共用同一 Coolify app(必獨立 application,各自 env / DB)

## End-to-end flow

```
1. developer 在 feature 分支寫程式 + 跑 dev server(localhost)
       ↓
2. 開 PR 進 main / staging
       ↓
3. CI(GitHub Actions)綠燈(對齊 05-CI/00-overview.md)
       ↓
4. reviewer approve + merge(squash)
       ↓
5. GitHub webhook → Coolify
       ↓
6. Coolify pull git + docker build(用 repo Dockerfile)
       ↓
7. 新 container 啟動 → healthcheck 等待 healthy
       ↓
8. healthy → Coolify 切流量(零停機 rolling)
       ↓
9. 不健康 → Coolify 自動回滾(見 06-rollback.md)
```

## Migration 時機

Alembic migration **必**在容器啟動時跑,**禁**手動 `alembic upgrade head` 在跳板機:

```Dockerfile
# Dockerfile (backend) — 不在 build 時跑
# CMD 改成 entrypoint script
CMD ["./entrypoint.sh"]
```

```bash
# entrypoint.sh
#!/bin/sh
set -e
uv run alembic upgrade head      # migration
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

注意:

- 容器**啟動**時跑(不是 build);多 replica 時各自跑會競爭 → Alembic 內建 lock 解決,但**禁**長時 migration(對齊 `04-databases/08-alembic.md § 一個 migration 一件事`)
- 大遷移(例 backfill 1M 列)拆 task 走 zero-downtime 流程(雙寫 → migrate → 下版移除舊欄)

## Webhook 設定

Coolify Application → Settings → Webhook URL:

```
https://coolify.<company>.internal/webhooks/<app-id>
```

GitHub Repo → Settings → Webhooks → Add webhook:
- Payload URL:Coolify webhook URL
- Content type:application/json
- Secret:Coolify 提供
- Events:Just the push event
- Active

## 部署視窗

production 部署視窗:

- ✅ 正常時段 09:00–17:00(可即時應變)
- ❌ 非工作時段、週末、長假前一天(沒人 standby)
- ❌ 公告凍結期(對齊組織政策)

緊急 hotfix 例外,**必**通知 oncall + 寫 `fixed.md`。

## 部署後驗證

每次部署後 30 分鐘內走:

- [ ] 主要 user journey 手測通過(登入 / 主要 CRUD)
- [ ] error log 無新增 5xx(對齊 `07-observability.md`)
- [ ] healthcheck 持續 healthy
- [ ] 第三方 callback(若有,例 SSO / payment)無中斷

任一失敗 → 走 `06-rollback.md`。
