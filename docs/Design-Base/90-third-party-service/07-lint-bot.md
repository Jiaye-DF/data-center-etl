# 07-lint-bot — Lint Bot / Reviewdog / Codecov

> **何時讀**:接 PR 自動化 reviewer / coverage bot 才讀。

PR comment 自動化工具,**輔助 reviewer 而非取代**。

---

## Reviewdog(lint 結果註記到 PR)

把 ruff / eslint / mypy 輸出轉成 PR inline comment,reviewer 一目瞭然。

```yaml
# .github/workflows/reviewdog.yml
name: reviewdog
on: [pull_request]
permissions:
  contents: read
  pull-requests: write

jobs:
  ruff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: reviewdog/action-setup@v1
      - uses: actions/setup-python@v5
        with:
          python-version-file: backend/pyproject.toml
      - uses: astral-sh/setup-uv@v4
      - working-directory: ./backend
        run: uv sync --frozen
      - working-directory: ./backend
        env:
          REVIEWDOG_GITHUB_API_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          uv run ruff check . --output-format=github | reviewdog -f=github-action-workflow -reporter=github-pr-review -fail-on-error=true

  eslint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: reviewdog/action-eslint@v1
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          reporter: github-pr-review
          workdir: frontend
          fail_on_error: true
```

## Codecov(coverage 視覺化)

```yaml
# .github/workflows/coverage.yml
- working-directory: ./backend
  run: uv run pytest --cov=app --cov-report=xml
- uses: codecov/codecov-action@v5
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    files: backend/coverage.xml
    flags: backend
```

```yaml
# .github/workflows/coverage.yml(frontend)
- working-directory: ./frontend
  run: npm run test -- --coverage
- uses: codecov/codecov-action@v5
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    files: frontend/coverage/lcov.info
    flags: frontend
```

`codecov.yml`:

```yaml
coverage:
  status:
    project:
      default:
        target: auto
        threshold: 1%        # 允許 1% 下滑(避免細微震盪擋 PR)
    patch:
      default:
        target: 80%          # 新改動的 lines 須 80% 覆蓋
```

## 規則

- 對應 lint 工具版本鎖定到 `00-overview/01-versions.md`(`ruff` / `eslint` / `mypy`)
- reviewdog `fail_on_error=true`(嚴格模式)— 對齊 `99-code-review/04-lint-checklist.md`
- coverage **僅**參考,**不**作為單一 gate(覆蓋率高 ≠ 測試品質好);reviewer 仍須讀測試
- bot 評論若 noise 過多 → reflect 候選收緊規則或調 sample rate

## 不要做

- ❌ 多套同類 bot 併存(reviewdog + super-linter + sonarcloud 重複,reviewer 疲勞)
- ❌ 把 bot comment 當作 review 通過依據(必須真人 reviewer,對齊 `05-CI/07-branch-protection.md`)
- ❌ 用 bot push commit 自動 fix(改 lint commit 應由 developer / reviewer 主動觸發,避免靜默改 code)
- ❌ codecov 設成必綠 gate 後又調 threshold 到 0(等於沒擋,assess 時誤判)
