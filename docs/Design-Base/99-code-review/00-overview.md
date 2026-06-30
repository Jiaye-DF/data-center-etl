# 00-overview — Code Review 收口入口

> **永遠讀**:任何 PR / 收口任務都讀。本資料夾為**所有 area 規範完成後的收口檢測**(對應 Anthropic「verify is highest leverage」)。

任何 area 任務在發 PR 前**必經**本資料夾檢測;通過視為 acceptance gate。

---

## Acceptance gate(永遠遵守)

PR merge 前必滿足:

1. **CI green** — 對齊 `05-CI/00-overview.md` 全 jobs 綠
2. **PR self-check** 全打勾 — `03-pr-self-check.md`(共同 + 後端 + 前端 + DB + 部署)
3. **Lint clean** — `04-lint-checklist.md`(warning 視同 error)
4. **Performance / Security / fixed.md** 抽查 — `05-performance-checklist.md` / `06-security-checklist.md` / `01-fixed-md.md`
5. **commit message 合格式** — `02-commit-message.md`
6. **≥ 1 reviewer 同意** — `07-review-process.md`

任一不通過 → **不**merge。

---

## 流程位置

```
寫程式 → 跑本地 lint / test → 開 PR
              │
              ▼
        CI(05-CI/*)→ 全綠
              │
              ▼
        PR self-check(99/03)→ 全勾
              │
              ▼
        reviewer 抽查 lint / perf / security checklist(99/04, 05, 06)
              │
              ▼
        approve + merge → main
```

---

## 違規處理

審查中發現違規:

1. PR 上 inline comment 指出規則參照(`docs/Design-Base/.../X.md § Y`)
2. 作者修正 + push 新 commit(**禁** `--force` / amend 已 push 的 commit)
3. 重大根因 → 寫 `fixed.md`(`01-fixed-md.md`)
4. 同類根因 ≥ 3 次 → reflect 候選升規(`01-propose/07-rule-evolution.md`)

## 子章節

- `01-fixed-md.md` — fixed.md 寫入規則(寫 fixed 才讀)
- `02-commit-message.md` — commit message 格式(任何 commit 讀)
- `03-pr-self-check.md` — PR self-check 列表(發 PR 前讀)
- `04-lint-checklist.md` — lint 通過判準
- `05-performance-checklist.md` — 效能抽查
- `06-security-checklist.md` — 安全抽查(OWASP / 機密 / CVE)
- `07-review-process.md` — review 流程(誰 review / 何時 merge / 衝突仲裁)
