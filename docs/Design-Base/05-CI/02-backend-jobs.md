# 02-backend-jobs — 後端 CI jobs

> **何時讀**:改 `.github/workflows/ci.yml` 的 backend jobs 才讀。

---

## Job 順序(必綠)

```
checkout → setup-python → setup-uv → uv sync --frozen → ruff → mypy → pytest(真 DB)→ alembic round-trip
```

```yaml
backend-test:
  runs-on: ubuntu-latest
  defaults:
    run:
      working-directory: ./backend
  services:
    postgres:
      image: postgres:17.2          # 對齊 00-overview/01-versions.md
      env:
        POSTGRES_PASSWORD: ci-only
        POSTGRES_DB: ci_test
        TZ: Asia/Taipei             # 對齊 00-overview/05-timezone.md
      ports: [5432:5432]
      options: >-
        --health-cmd pg_isready
        --health-interval 5s
        --health-timeout 5s
        --health-retries 10
  env:
    APP_ENV: development
    DATABASE_URL: postgresql+asyncpg://postgres:ci-only@localhost:5432/ci_test
    JWT_SECRET_KEY: ci-only-not-for-production
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version-file: backend/pyproject.toml   # requires-python 為單一來源
    - uses: astral-sh/setup-uv@v4
      with:
        version: "0.5.18"           # 對齊 00-overview/01-versions.md
    - run: uv sync --frozen
    - run: uv run ruff check .
    - run: uv run ruff format --check .
    - run: uv run mypy app
    - run: uv run alembic upgrade head
    - run: uv run alembic downgrade -1
    - run: uv run alembic upgrade head
    - run: uv run pytest -q
```

## 規則

- `uv sync --frozen`(**禁** `uv sync` / `pip install`,lock file 必逐字使用)
- `setup-python` 用 `python-version-file`,鎖到 `requires-python`(對齊 `00-overview/01-versions.md`)
- `ruff check` + `ruff format --check`(同套工具兩階段;**禁**用 `black` / `isort`)
- `mypy app`(scope 限 source,**禁**對 tests 開太嚴)
- alembic round-trip:`upgrade head` → `downgrade -1` → `upgrade head`,確保 migration 可逆(對齊 `04-databases/08-alembic.md`)
- pytest 用**真 DB**(對齊 `03-backend/07-testing.md`),**禁** mock SQL

## services 與 env

- 用 GitHub Actions `services:` 拉 `postgres:17.2`(image tag 對齊 `00-overview/01-versions.md`)
- env 用 `APP_ENV=development` + `JWT_SECRET_KEY=ci-only-not-for-production`(避開 fail-fast,對齊 `00-overview/03-env-layers.md` APP_ENV 三值)
- 機密 env(若需第三方 sandbox 測)走 GitHub Secrets,見 `08-secrets-and-oidc.md`
