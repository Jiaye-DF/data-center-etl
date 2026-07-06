---
id: task-012
title: Docker 化(etl_ prefix image + redis / worker / scheduler 服務)
status: done
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

- [x] `docker compose config` 解析成功(exit 0)
- [x] `grep -cE "image:\s*etl_" docker-compose.yml` ≥ 2 且 `! grep -nE "image:\s*(frontend|backend|worker|scheduler)\s*$" docker-compose.yml`(自建 image 全 etl_ prefix;實測 count=4)
- [x] `grep -q "redis" docker-compose.yml && grep -qE "redis:[0-9]" docker-compose.yml`(redis 服務存在且鎖版 `redis:7.4.2-alpine`)
- [x] `docker compose up -d` 後所有服務 healthy(`docker compose ps` 無 unhealthy;本地手驗記錄)
- [x] `! grep -riE "(password|secret)\s*=\s*[^\s#$]{8,}" .env.example`(範本無真實機密)

## 本地手驗記錄(2026-07-03,Git Bash + Docker 29.2.1)

- `docker compose build` + `docker compose up -d` 全部成功;`docker compose ps` 六服務皆 `(healthy)`:
  `etl_backend` / `etl_frontend` / `etl_worker` / `etl_scheduler`(共用 image `etl_backend`)/ `etl_postgres`(postgres:18-alpine)/ `etl_redis`(redis:7.4.2-alpine)
- `curl http://localhost:8000/api/v1/health` → 200(db ok);`curl http://localhost:3000/` → 200
- 端到端煙霧測試:backend 容器內 `run_etl.kiq(...)` 入列 → worker 消費 → `etl_runs` 寫入 `status=success`,redis 佇列歸零
- 已知未決:worker 閒置時 taskiq 子行程每 ~5 秒 reload(redis-py 8 預設 socket_timeout 與 taskiq-redis ListQueueBroker 不相容;修法在 task-007 的 `broker.py`,不在本 task 白名單)→ 見 `fixed.md §19`
- Dockerfile 版本鎖定線偏離規範表(python 3.14.1-slim / uv 0.11.20,依 pyproject / uv.lock 為準)→ 見 `fixed.md §9`

## 必讀檔(Just-in-time)

- `docs/Design-Base/06-Coolify-CD/00-overview.md` + `01-compose.md`
- `docs/Design-Base/06-Coolify-CD/02-dockerfile-backend.md`
- `docs/Design-Base/00-overview/03-env-layers.md` + `02-secrets.md`
- `docs/Design-Base/00-overview/05-timezone.md`(container TZ)
