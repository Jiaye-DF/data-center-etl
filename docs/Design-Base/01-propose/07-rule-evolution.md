# 07-rule-evolution — 規則演進閉環

> **何時讀**:跑 `/reflect-rules` / 升規評估 / 規則被推翻時讀。

`fixed.md` → `/reflect-rules` → `docs/Design-Base/*` 升級的**三段式回流**。本機制讓規範**自適應演進**而非死文件。

---

## 三段式

### A. 觀察期(每次 commit)

- 違規 / bug → 寫 `fixed.md`(格式見 `04-fixed-format.md`)
- 規範被推翻 → `tasks-v*.md` checkbox 補「— 已改為 xxx,見 fixed.md §N」
- 規範彼此衝突 → 同樣寫進 `fixed.md`,根因標「規範矛盾」

### B. 反思期(`/reflect-rules` 觸發)

- 讀 `docs/Tasks/v*/fixed.md`(全版本)
- 找 pattern:
  - **同規則 ≥ 3 次違反** → 規則太弱 / 太抽象 / 沒 lint 強制 → 候選**強化**
  - **同類根因跨 ≥ 2 版本** → 沒對應規則 → 候選**新規則**
  - **規範彼此矛盾** → 候選**修正**
  - **規則沒違反過 ≥ 6 個月** → 候選**移除**(可能多餘)
- 產出 `docs/Tasks/reflect/reflect-report-{YYMMDDHHMMSS}.md`

### C. 升級期(user 批准後)

- 改 `docs/Design-Base/*` 對應檔(對齊正交原則:新規對應「獨立子任務情境」才獨立檔)
- commit `(AI) Modify: 升級 <規則>(基於 fixed §N)`
- 該檔頭加變更紀錄(日期 + 來源 fixed §N)
- 棄用規則 → 該檔加 `> 狀態:已棄用,見 fixed.md vX.Y.Z §N`
- 同步 `99-code-review/` 對應 checklist 條目(若可機械驗證)

---

## 觸發條件

- **月度自動** — 每月 1 號(預設)
- **版本結束必觸發** — 該版本 PR merge 前
- **同類條目觸發** — `fixed.md` 同類 ≥ 3 個跨 ≥ 2 版本

## 升級規則

- 必經 PR + ≥ 1 reviewer 同意
- **不破壞 backward-compat** — 新規則只規範**該 commit 之後**的 code(既有 code 不必補,標明 grandfather)
- **新增規則優先合進既有檔**;構成獨立子任務情境才獨立檔
- 棄用既有規則須在 `reflect-report` 明確列出原因 + 影響範圍
- 升級**禁**靜悄悄做,必走 reflect-report → user → PR

---

## reflect-report 格式

```markdown
# reflect-report-{YYMMDDHHMMSS}

## 候選 1 — <規則名 / 主題>

- **類型**:強化 / 新增 / 修正 / 棄用
- **來源**:fixed.md `vX.Y.Z §N`、`vM.K.L §L`...(列全)
- **pattern**:<為什麼成 pattern;次數 / 跨版本 / 同類根因>
- **建議**:<具體規則文字 / 落腳檔>
- **影響**:<是否破壞 backward / 既有 code 是否合規 / 需補哪些檔>
- **driver**:<提議的 reviewer / 規則 owner>

## 候選 2 — ...
```

## reflect 收口

user 在 PR 上對每個候選決議:
- ✅ 採納 → 開 task 走 C 段升級
- ❌ 拒絕 → 在 reflect-report 條目下記「拒絕原因」(也是學習素材)
- 🕐 暫緩 → 帶到下次 reflect 重評
