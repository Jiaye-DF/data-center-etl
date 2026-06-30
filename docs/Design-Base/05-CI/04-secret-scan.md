# 04-secret-scan — 機密掃描

> **何時讀**:改 secret-scan job / 處理 gitleaks 命中才讀。對應規則見 `00-overview/02-secrets.md § 機密**不可**曾 commit`。

工具:**gitleaks**(主)+ trufflehog(可選輔助)。

---

## Job 範例

```yaml
secret-scan:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0      # 必須 full history,gitleaks 才能掃整個歷史
    - uses: gitleaks/gitleaks-action@v2
      env:
        GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}   # org 用戶必填,個人免費
      with:
        config-path: .gitleaks.toml
```

## `.gitleaks.toml`(專案層 config)

```toml
title = "<project> gitleaks config"

[extend]
useDefault = true     # 繼承 gitleaks 內建規則

[allowlist]
description = "白名單"
paths = [
  '''(.*\.)?env\..*\.example''',   # .env.*.example 內 placeholder 可放
  '''docs/.*\.md''',               # 範例文件不掃
]
regexes = [
  '''development-only-not-for-production''',     # 預設 development placeholder
  '''<change-me>''',
]
```

## 觸發

- 每次 push / PR(對齊 `00-overview.md § 觸發策略`)
- **禁** `continue-on-error: true`(機密外洩零容忍)

## 命中處理流程

gitleaks 命中 → 走 `00-overview/02-secrets.md § 外洩 incident 流程`:

1. 立即 rotate 該 secret(全環境)
2. 撤銷舊值
3. 寫 `fixed.md`:外洩源 / 影響範圍
4. 補本 `.gitleaks.toml` 規則防再犯(若是新類型 secret)
5. 用 `git filter-repo` 清歷史(team commit 全 force-push 過 — **僅**此情境允許,其他禁)

## trufflehog(可選)

若要掃 verified secret(實際可用而非看起來像)→ 加 trufflehog:

```yaml
- uses: trufflesecurity/trufflehog@main
  with:
    extra_args: --only-verified
```

不必同 PR 跑兩個工具;trufflehog 適合 nightly 全 repo 掃,gitleaks 適合 PR diff 即時擋。

## 與其他 scan 區隔

- 機密外洩 → 本檔(gitleaks)
- 已知 CVE → `03-dependency-audit.md`
- SAST(程式碼漏洞)→ `05-security-scan.md`
