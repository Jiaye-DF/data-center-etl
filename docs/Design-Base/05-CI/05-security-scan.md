# 05-security-scan — SAST + Container scan

> **何時讀**:改 security-scan job / 處理 SAST 警告才讀。

兩段:**SAST**(程式碼層,semgrep)+ **container scan**(image 層,trivy)。

---

## SAST(semgrep)

掃常見 anti-pattern / OWASP / 自訂規則。

```yaml
sast:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: returntocorp/semgrep-action@v1
      with:
        config: >-
          p/owasp-top-ten
          p/python
          p/typescript
          p/react
          p/security-audit
```

容忍度:

- `ERROR` 等級 → block PR
- `WARNING` → 不擋 PR,但寫進 PR comment(reviewer 評估)
- `INFO` → 不擋

## Container scan(trivy)

掃 Docker image 已知 CVE / mis-config。在 build image 後或 nightly 跑。

```yaml
container-scan:
  runs-on: ubuntu-latest
  needs: [build]   # 假設有 build job 產生 image
  steps:
    - uses: actions/checkout@v4
    - uses: aquasecurity/trivy-action@master
      with:
        image-ref: '<registry>/<image>:${{ github.sha }}'
        severity: 'HIGH,CRITICAL'
        exit-code: '1'
        ignore-unfixed: true   # 上游無修為止暫不擋
```

容忍度:

- `HIGH` / `CRITICAL` 且**有修** → block(`exit-code: 1` + `ignore-unfixed: true`)
- `MEDIUM` / `LOW` → 不擋,nightly 全掃時記錄
- 上游無修 → ignore,但寫 `fixed.md` 註記重檢日期

## 自訂 semgrep 規則(專案專屬)

若有 repo-specific anti-pattern(例:某內部 SDK 不可亂用),寫於:

```
.semgrep/
└── rules/
    ├── no-direct-fetch.yml   # 對應 02-frontend/02-api-and-state.md
    ├── no-raw-sql.yml        # 對應 04-databases/04-sql-safety.md
    └── ...
```

對應規則參照 `docs/Design-Base/*` 的硬規則,**目的是 lint 強制**(對齊 `01-propose/07-rule-evolution.md` 的「同規則 ≥ 3 次違反 → 候選強化」)。

## 例外

例外規則 / ignore 清單必寫進 `.semgrepignore` / `.trivyignore`,**並**寫 `fixed.md`:

```
# .trivyignore
CVE-2025-XXXX  # 對應 fixed.md §N,理由:上游無 fix,影響範圍評估後可接受;每月重檢
```

## 跨 scan 區隔

- 機密外洩 → `04-secret-scan.md`
- 套件 known CVE(non-image)→ `03-dependency-audit.md`
- 程式碼層漏洞 → 本檔 SAST
- Docker image 漏洞 → 本檔 container scan
