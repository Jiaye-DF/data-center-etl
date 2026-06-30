# 01-frontend-jobs — 前端 CI jobs

> **何時讀**:改 `.github/workflows/ci.yml` 的 frontend jobs 才讀。

---

## Job 順序(必綠)

```
checkout → setup-node → npm ci → lint → typecheck → test → build
```

```yaml
frontend-test:
  runs-on: ubuntu-latest
  defaults:
    run:
      working-directory: ./frontend
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version-file: frontend/package.json   # engines.node 為單一來源
        cache: npm
        cache-dependency-path: frontend/package-lock.json
    - run: npm ci
    - run: npm run lint
    - run: npm run typecheck
    - run: npm run test -- --run
    - run: npm run build
```

## script 對應(`frontend/package.json`)

```json
{
  "scripts": {
    "lint": "eslint . --max-warnings=0",
    "typecheck": "tsc --noEmit",
    "test": "vitest",
    "build": "vite build"  // 或 next build
  }
}
```

## 規則

- `npm ci`(**禁** `npm install`,lock file 必逐字使用)
- `setup-node` 用 `node-version-file`,鎖到 `engines.node`(對齊 `00-overview/01-versions.md`)
- `eslint --max-warnings=0` — warning 視同 error
- `tsc --noEmit` — 純 typecheck,**禁**走 build emit
- `vitest --run`(**禁** watch 模式跑 CI)
- `npm run build` 失敗 → 視為 ci 失敗(避免「能跑 development 但部署掛」)

## 快取

- `actions/setup-node` `cache: npm` 走 `package-lock.json` hash
- **禁** 自建 cache 步驟(複雜 + 容易 stale)

## E2E

E2E(Playwright)放獨立 workflow,見 `06-e2e.md`,**不**併入本 ci job。
