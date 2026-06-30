# 00-overview — Coolify 部署入口

> **何時讀**:任何部署 / Dockerfile / compose 任務都讀;具體細節依任務載入子檔。

本企業現況:**無 K8s**,部署主走 **Coolify**(自架 PaaS)+ **Docker Compose**。本資料夾規範 compose / Dockerfile / env / rollback。

---

## 部署模型(永遠遵守)

```
git push origin main
   │
   ▼
GitHub webhook
   │
   ▼
Coolify(自架,自架機器拉 git)
   │
   │ docker build(用 repo 內 Dockerfile)
   │ 或 docker compose(用 repo 內 docker-compose.yml)
   ▼
新容器啟動
   │
   │ healthcheck(/api/v1/health)pass
   ▼
切流量(Coolify 內建零停機)
```

- Coolify 從 git 拉,**禁** CI 推 image(GitHub Actions 不負責 deploy)
- 主分支 `main` → production;`staging` 分支 → staging(見 `05-deploy-flow.md`)
- 機密由 Coolify 注入,**禁** `.env*` 檔放容器內(見 `04-env-and-secrets.md`)

## 服務組成(典型)

```
<project>/
├── docker-compose.yml          # Coolify 讀;見 01-compose.md
├── backend/
│   └── Dockerfile              # 見 02-dockerfile-backend.md
├── frontend/
│   └── Dockerfile              # 見 03-dockerfile-frontend.md
└── .env.<env>.example          # placeholder;實機密 Coolify 注入
```

services 必含:
- `backend`(FastAPI)
- `frontend`(Vite=nginx 或 Next standalone)
- `postgres`(用 `POSTGRES_VERSION` env)
- 視專案加 `redis` / `worker` 等

## 採用方 bootstrap(init-project 後**必補**)

`Skills/init-project/` skill **不**產出本資料夾規範的部署檔(skill 明示邊界,見 `Skills/init-project/SKILL.md`)。
scaffold → push 到 GitHub → Coolify 拉 → 若以下檔未補,**deploy 直接失敗**(找不到 build context)。

採用方在第一次 push 到 Coolify 前必須手動補上:

| 檔案 | 對應規範子章節 | 必要性 |
| --- | --- | --- |
| `docker-compose.yml` | `01-compose.md` | 必要 — Coolify 讀此檔判定 services |
| `backend/Dockerfile` | `02-dockerfile-backend.md` | 必要 — backend service build 來源 |
| `frontend/Dockerfile` | `03-dockerfile-frontend.md` | 必要 — frontend service build 來源 |
| Coolify 端 env 注入 | `04-env-and-secrets.md` | 必要 — `DATABASE_URL` / `JWT_SECRET_KEY` / `CORS_ORIGINS` 等 |
| 部署流程驗收 | `05-deploy-flow.md` | 必跑 — push → webhook → healthcheck → 切流量 |

驗收:
1. `docker compose -f docker-compose.yml config` 通過(yaml 合法、所有 service / image / env 解析得到)
2. 連上 Coolify 後,`curl <coolify-host>/api/{api_version}/health` 回 200
3. Coolify 後台首次 deploy 顯示 healthcheck pass、流量切換成功

未補完 push,Coolify 會在 build 階段 ERR(找不到 Dockerfile)或 healthcheck timeout(service 沒起來)。

## healthcheck(永遠遵守)

每 service 必有 `healthcheck`(見 `01-compose.md`):
- backend → `GET /api/v1/health`(fastapi 端點,**必**回 200)
- frontend → 視框架(nginx `/` / next `/`)
- postgres → `pg_isready`

健康才切流量;不健康 Coolify 自動回滾。

## 子章節

- `01-compose.md` — `docker-compose.yml` 模板
- `02-dockerfile-backend.md` — backend multi-stage Dockerfile
- `03-dockerfile-frontend.md` — frontend Dockerfile(Vite=nginx / Next=standalone)
- `04-env-and-secrets.md` — Coolify env 注入 + Secrets vs 環境變數
- `05-deploy-flow.md` — push → webhook → build → deploy
- `06-rollback.md` — Coolify rollback + 緊急 git revert
- `07-observability.md` — log / metric / Sentry
- `08-domains-and-tls.md` — 自動 TLS / domain / preview env
