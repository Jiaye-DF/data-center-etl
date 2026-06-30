# 00-overview — Propose / Tasks / Multi-agent 入口

> **何時讀**:啟動新版本 / 拆 tasks / 寫 fixed / multi-agent 並行才讀。

本資料夾規範**版本工作流**:User 寫 propose → Agent 拆 tasks → Multi-agent 執行 → fixed → reflect 升級規範。

---

## 工作流關係

```
propose-v{X.Y.Z}.md          tasks-v{X.Y.Z}.md         fixed.md                 reflect-report-*.md
(User 寫 — 版本目標)    →    (Agent 拆 — 執行單元)  →   (執行中累積根因)   →    (版本結束 / 月度回流)
                                  ↓
                                tasks/<task-N>.md(細節)
                                  ↓
                                CHANGELOG.md(release 前彙整 user-facing)
```

> 版本檔名一律 **3-digit semver** `vX.Y.Z`(例 `propose-v1.0.0.md` / `tasks-v1.1.0.md`);資料夾同樣 `docs/Tasks/v1.0.0/`。判準見 `05-version-bump.md`。

## 角色分工

| 文件 | 角色 | 由誰寫 | 讀 |
| --- | --- | --- | --- |
| `propose-v*.md` | 版本目標 | **User** | `01-propose-format.md` |
| `tasks-v*.md` + `tasks/*.md` | 執行單元 | **Agent**(orchestrator) | `02-task-decomposition.md` |
| `fixed.md` | 規範違反 / bug 根因 | Agent 累積 | `04-fixed-format.md` |
| `CHANGELOG.md` | 對外 user-facing | Agent / User | `06-changelog.md` |
| `reflect-report-*.md` | 規範升級候選 | `/reflect-rules` | `07-rule-evolution.md` |

## Multi-agent 摘要

Orchestrator-Workers:User 寫 propose → orchestrator(`/propose-to-tasks`)拆 tasks → workers 並行認領 → orchestrator 收口(`/scan-project` + `/reflect-rules`)。細節見 `03-multi-agent-flow.md`。

## 版本判準摘要

minor 以上才寫 propose;patch 直接修 + `fixed.md`。判準見 `05-version-bump.md`。

---

## 子章節

- `01-propose-format.md` — propose-v*.md 格式(User 寫)
- `02-task-decomposition.md` — 拆 task 方法論(粒度 / 依賴 / 並行)
- `03-multi-agent-flow.md` — Orchestrator-Workers 協議 + 衝突解決
- `04-fixed-format.md` — fixed.md 條目格式
- `05-version-bump.md` — major / minor / patch 判準
- `06-changelog.md` — 對外 CHANGELOG 格式
- `07-rule-evolution.md` — fixed → reflect → docs/Design-Base 升級閉環
