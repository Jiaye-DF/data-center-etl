---
id: task-012
title: Docker 化(etl_ prefix image + redis / worker / scheduler 服務)
status: pending
parallel: true
depends_on: [task-007]
affected_files:
  - docker-compose.yml
  - backend/Dockerfile
  - .env.example
estimated_hours: 2
---

## 目標

補齊 v1.1.0 的容器組成:compose 新增 `redis`、`worker`(taskiq worker)、`scheduler` 服務;**所有自建 image 命名一律 `etl_` prefix**(`etl_frontend` / `etl_backend` / `etl_worker` / `etl_scheduler`);官方 image(postgres / redis)以 `container_name: etl_*` 標示。`docker compose up` 本地一鍵起跑全部服務並通過 healthcheck。

## 範圍要點

- 應用服務維持單純 `frontend` / `backend` 兩個(既有),worker / scheduler 共用 backend image(`etl_backend`)不同 command,或於 backend/Dockerfile 加 stage —— 擇一,以不重複 build 為準。
- redis 服務加 healthcheck;worker / scheduler `depends_on` redis + postgres healthy。
- `.env.example` 補 v1.1.0 新 env(`REDIS_URL` / `INIT_ADMIN_*` / `SOURCE_DB_*` / `TARGET_DB_*` / SSO 設定),值一律佔位符,**禁**真實機密(`02-secrets.md`);`localhost` 僅本地層(`03-env-layers.md`)。
- 版本鎖定:redis image 帶明確版號 tag(`06-Coolify-CD/01-compose.md`)。

## Acceptance

- [ ] `docker compose config` 解析成功(exit 0)
- [ ] `grep -cE "image:\s*etl_" docker-compose.yml` ≥ 2 且 `! grep -nE "image:\s*(frontend|backend|worker|scheduler)\s*$" docker-compose.yml`(自建 image 全 etl_ prefix)
- [ ] `grep -q "redis" docker-compose.yml && grep -qE "redis:[0-9]" docker-compose.yml`(redis 服務存在且鎖版)
- [ ] `docker compose up -d` 後所有服務 healthy(`docker compose ps` 無 unhealthy;本地手驗記錄)
- [ ] `! grep -riE "(password|secret)\s*=\s*[^\s#$]{8,}" .env.example`(範本無真實機密)

## 必讀檔(Just-in-time)

- `docs/Design-Base/06-Coolify-CD/00-overview.md` + `01-compose.md`
- `docs/Design-Base/06-Coolify-CD/02-dockerfile-backend.md`
- `docs/Design-Base/00-overview/03-env-layers.md` + `02-secrets.md`
- `docs/Design-Base/00-overview/05-timezone.md`(container TZ)
