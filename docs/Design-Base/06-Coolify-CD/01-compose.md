# 01-compose — docker-compose.yml 模板

> **何時讀**:寫 / 改 `docker-compose.yml` 才讀。

Coolify 直接讀 repo 內 `docker-compose.yml`。版本鎖定走 `.env` 變數,對齊 `00-overview/01-versions.md`。

---

## 模板

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      APP_ENV: ${APP_ENV}
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      CORS_ORIGINS: ${CORS_ORIGINS}
      TZ: Asia/Taipei
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/api/v1/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      TZ: Asia/Taipei
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:80/"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  postgres:
    image: postgres:${POSTGRES_VERSION}        # 對齊 00-overview/01-versions.md
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
      TZ: Asia/Taipei
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped

volumes:
  postgres_data:
```

## 規則

- **鎖版**:image tag 必走 `${SERVICE_VERSION}` env(對齊 `00-overview/01-versions.md`),**禁**直寫 `postgres:17`
- **healthcheck**:每 service 必有;backend `/api/v1/health` 為 acceptance gate
- **depends_on**:用 `condition: service_healthy`,**禁** `service_started`(只看啟動不看健康)
- **TZ**:每 service 必設 `TZ: Asia/Taipei`(對齊 `00-overview/05-timezone.md`)
- **volumes**:DB 必持久化(named volume);**禁**用 host bind mount(Coolify 跨機難遷移)
- **網路**:預設同 compose 內走預設 network,**禁**手動 `network_mode: host`
- **port mapping**:本檔不對外開 port;對外走 Coolify 反向代理(見 `08-domains-and-tls.md`)

## 資源限制(可選)

production 視需要加 `deploy.resources.limits`:

```yaml
backend:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 1G
```

## development 變體

本地 development 用 `docker-compose.development.yml`,只跑 `postgres`(後端 / 前端走 dev server,對齊 `00-overview/03-env-layers.md § development = localhost`):

```yaml
# docker-compose.development.yml
services:
  postgres:
    image: postgres:${POSTGRES_VERSION}
    ports: ["5432:5432"]   # 開給本機 dev server
    environment:
      POSTGRES_PASSWORD: development
      POSTGRES_DB: <project>_development
      TZ: Asia/Taipei
    volumes:
      - postgres_development_data:/var/lib/postgresql/data

volumes:
  postgres_development_data:
```
