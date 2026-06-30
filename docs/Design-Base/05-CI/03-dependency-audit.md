# 03-dependency-audit — 依賴掃描

> **何時讀**:改 audit job / 處理 CVE 警告才讀。

掃 CVE / known vulnerability。前端走 `npm audit`,後端走 `pip-audit`(走 `uv` 的 `pip-audit` plugin 或 GitHub Action)。

---

## Job 範例

```yaml
dependency-audit:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version-file: frontend/package.json
        cache: npm
        cache-dependency-path: frontend/package-lock.json
    - name: npm audit
      working-directory: ./frontend
      run: npm audit --audit-level=high
      continue-on-error: true        # 過渡期;見下方時程
    - uses: actions/setup-python@v5
      with:
        python-version-file: backend/pyproject.toml
    - uses: astral-sh/setup-uv@v4
    - name: pip-audit
      working-directory: ./backend
      run: |
        uv tool install pip-audit
        uv run pip-audit
      continue-on-error: true        # 過渡期
```

## 容忍度

- `npm audit --audit-level=high` — 只看 high / critical(low / moderate 暫不擋 PR)
- `pip-audit` — 預設掃 known CVE
- 過渡期 `continue-on-error: true`;有時程**必改** `false`(見下方)

## continue-on-error 退場時程

新專案啟動時 `true`(避開立即被 known CVE 卡住),但**必須**有退場計畫:

| 階段 | 設定 | 條件 |
| --- | --- | --- |
| 啟動初期(< 1 個月)| `continue-on-error: true` | 收集現有 CVE 基線,寫進 `fixed.md` 計畫升級 |
| 成熟期(≥ 1 個月)| `continue-on-error: false` | 已清理高危 CVE,新引入立即擋 |

時程超過 3 個月仍 `true` → reflect 觸發,評估是否規範升級(對應 `01-propose/07-rule-evolution.md`)。

## 例外處理

無法立即升版的 CVE(上游 fix 未出 / breaking)→ 加 ignore 清單 + 寫進 `fixed.md`:

```yaml
# .npmrc 或 audit-ci 設定
{
  "ignore": ["GHSA-xxxx-xxxx-xxxx"]   # 對應 fixed.md §N
}
```

`fixed.md` 必含理由 + 重檢日期(每月 reflect 時驗證是否仍需 ignore)。

## 跨 area 對應

- 升級套件 → 對齊 `00-overview/01-versions.md` 鎖定原則(獨立 commit + 表更新 + lock file)
- 機密外洩 → 走 `04-secret-scan.md`(本檔不掃機密)
- SAST → 走 `05-security-scan.md`(本檔不掃程式碼漏洞)
