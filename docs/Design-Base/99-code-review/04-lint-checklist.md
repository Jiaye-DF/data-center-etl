# 04-lint-checklist — Lint 通過判準

> **何時讀**:跑 lint / 處理 lint warning 才讀。

各 area lint 工具 + 容忍度;**warning 視同 error**(零容忍)。

---

## 工具(對齊 `00-overview/01-versions.md`)

| Area | 工具 | 命令 | 設定檔 |
| --- | --- | --- | --- |
| Frontend(JS/TS) | `eslint` 9 | `npm run lint` | `eslint.config.js`(flat config) |
| Frontend(format) | `prettier` 3 | `npm run format -- --check` | `.prettierrc` |
| Backend(lint + format) | `ruff` 0.9 | `uv run ruff check . && uv run ruff format --check .` | `pyproject.toml [tool.ruff]` |
| Backend(typecheck) | `mypy` 1.14 | `uv run mypy app` | `pyproject.toml [tool.mypy]` |
| TypeScript | `tsc --noEmit` | `npm run typecheck` | `tsconfig.json` |

## 容忍度(永遠遵守)

- **任何 warning** 視同 error(eslint `--max-warnings=0`、ruff 預設視 warning 為 fail)
- **禁** disable rule 為「過 lint」;只允許情境性 disable + 同行 / 上一行註解理由:
  ```ts
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- 第三方 SDK 強制 any,改 unknown 後加守衛
  function adapt(x: any): MyType { ... }
  ```
  ```python
  result = data["x"]  # noqa: B009 -- 第三方 dict 必經 key access
  ```
- **禁**檔案層 disable(`/* eslint-disable */` 整檔)
- 沒寫理由的 disable → reviewer 必擋

## 必有 rule 集

### Frontend(eslint)

最少:`@typescript-eslint/recommended` + `eslint-plugin-react` + `eslint-plugin-react-hooks` + `eslint-plugin-react-refresh`(Vite)。

對應 `02-frontend/00-overview.md` 的硬規則,可加 lint:

- `@typescript-eslint/no-explicit-any` = `error`
- `@typescript-eslint/explicit-function-return-type`(視專案)
- `react-hooks/exhaustive-deps` = `error`(`useCallback` / `useMemo` / `useEffect` 依賴正確)

### Backend(ruff)

```toml
[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = [
    "E", "F",        # pycodestyle / pyflakes
    "I",             # isort
    "B",             # bugbear
    "ASYNC",         # async issues
    "S",             # bandit(安全)
    "UP",            # pyupgrade
    "RET",           # return
    "SIM",           # simplify
    "T20",           # 禁 print
    "RUF",           # ruff-specific
]
ignore = ["E501"]    # line-length 走 formatter

[tool.ruff.format]
quote-style = "double"
```

### Backend(mypy)

```toml
[tool.mypy]
python_version = "3.14"
strict = true
warn_unused_ignores = true
disallow_any_explicit = true
disallow_any_generics = true
```

## 修法

lint 失敗(本地)→ 先試自動修:

- `npm run lint -- --fix`
- `uv run ruff check --fix .`
- `uv run ruff format .`

仍剩問題 → 修 code(**禁**為了過 lint 寫 disable)。

## 與其他 checklist 的差異

| | lint(本檔) | performance(05) | security(06) |
| --- | --- | --- | --- |
| 自動 | ✓ CI 卡 | 部分(query plan 抽查需手動) | 部分(SAST 自動,審查需手動) |
| 屬性 | 風格 / 型別 / 明顯 bug | 行為 | 行為 + 風險 |
| 容忍 | 零 warning | 抽查 | 零 high CVE |
