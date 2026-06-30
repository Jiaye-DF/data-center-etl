# prompts/

跨工具(Claude Code / Codex / Cursor / Cline / Aider)agent skill 入口。本資料夾每份 `*.md` = 一個可被各 IDE 載入的 skill,對齊 `Harness-Engineering/AGENTS.md § Agent Capabilities Baseline`。

> **不是規範本體**:規範在 `docs/Design-Base/`。本資料夾只是「呼叫規範的入口」。改規則動 `docs/Design-Base/`,**不動本資料夾**(除非新增 / 改 skill workflow 本身)。

---

## 索引

| 檔 | type | 何時觸發 | 用途 |
| --- | --- | --- | --- |
| `propose-to-tasks.md` | agent | user 寫完 `propose-v{X.Y.Z}.md` | Orchestrator 拆 multi-agent 可並行 tasks |
| `scan-project.md` | agent | user 說「掃描 / scan / code review / 找問題」 | 累積式問題清單(R-xxx / AD-xxx) |
| `reflect-rules.md` | agent | 版本結束 / 月度週期 | 讀全版本 `fixed.md` 找 pattern → 候選升規 |

> `init-project` 已遷移為 Claude Code 原生 skill,獨立分發於 `Harness-Engineering/Skills/init-project/`(自包含,可 push 到 GitHub 給其他 user 安裝)。本資料夾不再放 init-project。

完整流程:`/init-project` → user 寫 propose → `/propose-to-tasks` 拆 task → workers 跑 task → `/scan-project` 收口 → `/reflect-rules` 升規。

---

## 檔案格式

每份 skill 必含 YAML frontmatter:

```yaml
---
name: <kebab-case 名稱>
type: workflow | agent
description: <一句話 + 觸發詞;當 user 說「...」時觸發>
when_not_to_use:
  - <情境 1>
  - <情境 2>
inputs:
  - name: <param>
    type: <type>
    required: true | false
    default: <value>
capabilities_required:
  - file_read | file_write | shell_exec
---
```

frontmatter 後接內容區塊(順序固定):

- `## 身分` — agent 自我定位(影響輸出風格)
- `## 語言偏好` — `zh-TW`(本企業預設)
- `## 風格` — 一兩句修飾
- `## 心法` — 高階原則(編號清單)
- `## 前置讀取` — 必載入的規範檔(對齊 `docs/Design-Base/README.md` 索引)
- `## 收集參數`(workflow 類)
- `## 執行步驟`(workflow / agent 類)
- `## 產出`(寫檔的 skill 必含)
- `## Acceptance`(必跑) — 機械可驗證的條件,任一失敗不報告完成
- `## 自我約束` — 禁忌列表

---

## 各 IDE 入口對照

| 工具 | 入口檔 | 載入方式 |
| --- | --- | --- |
| Claude Code | `.claude/commands/<name>.md` | 檔內單行 `@docs/Prompts/<name>.md`(import) |
| Codex CLI | session 開頭附 `docs/Prompts/<name>.md` | 直讀 |
| Cursor | `.cursor/rules/` 引用 + chat 拖檔 | 規則 / 引用 |
| Cline | `.clinerules/` 引用 | 規則 |
| Aider | `--read docs/Prompts/<name>.md` | CLI 參數 |

**單一來源**:本資料夾為 single source。各工具入口走 import / 直讀,**禁**複製內容(改規則只改本資料夾)。

採用方專案落地時,本資料夾整份複製為 `<project>/docs/Prompts/`(對齊 `Harness-Engineering/README.md § 使用協議`);Harness-Engineering 內路徑為 `Harness-Engineering/prompts/`,專案內統一改為 `docs/Prompts/`(駝峰大寫 P,跨工具慣例)。

---

## Capabilities Baseline

本資料夾 skill 以「能讀檔 / 能寫檔 / 能執行 shell」為地板(對齊 `Harness-Engineering/AGENTS.md`)。工具更強(plan mode / sub-agent / hook / skill)只可**加強**遵守程度,**不可**降低。純 chat 介面無 file write → 本規範不適用,需手動執行。

---

## 新增 / 修改 skill

1. 對應 `docs/Design-Base/*` 已有規範 → skill **只呼叫,不重述**(避免雙處維護)
2. 規則範圍變動 → 改 `docs/Design-Base/*`,本資料夾 skill 同步更新「前置讀取」段
3. 新 skill 必補:
   - frontmatter(完整 schema 全欄)
   - `## Acceptance`(可機械驗證,**禁**「跑得起來」「沒 bug」)
   - 在本檔索引表加一列
4. commit message:`(AI) Add: prompts/<name>.md skill`(對齊 `99-code-review/02-commit-message.md`)
5. 棄用 skill → 該檔頭加 `> 狀態:已棄用,見 fixed.md vX.Y.Z §N`,索引表對應條目劃 `~~刪線~~`(不直接移除,留歷史)
