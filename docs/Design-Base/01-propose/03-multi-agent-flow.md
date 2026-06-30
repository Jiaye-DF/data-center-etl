# 03-multi-agent-flow — Orchestrator-Workers 協議

> **何時讀**:啟用 multi-agent 並行才讀(單 agent 工作不必)。

---

## Pattern

```
User
  │ 寫 propose-v{X.Y.Z}.md
  ▼
Orchestrator(/propose-to-tasks)
  │ 拆 tasks-v{X.Y.Z}.md + tasks/*.md
  ▼
Worker A    Worker B    Worker C    ← 並行認領 task
  │           │           │
  │ 寫程式 + 跑 Acceptance + 標 done
  │ 違規 / bug → 寫 fixed.md
  ▼           ▼           ▼
全部 done
  │
  ▼
Orchestrator(收口)
  │ /scan-project 全域檢測
  │ /reflect-rules 升規候選
  ▼
PR → review → merge
```

---

## Worker 認領協議

1. 讀 `tasks-v{X.Y.Z}.md`,挑 `status: pending` + `affected_files` **不**衝突的 task
2. 改該 task 檔 `status: in_progress` + 在 `tasks-v{X.Y.Z}.md` 註記 worker id(例 `worker: claude-A`)
3. 依 task 檔 `## 必讀檔(Just-in-time)` 載入規範檔
4. 執行 → 跑 Acceptance → **全綠**才標 `status: done`
5. 違規 / bug → 寫 `fixed.md`(`04-fixed-format.md`)
6. commit message 加 `[task-NNN]` tag

## 衝突偵測

- **同檔互鎖**:worker 認領前掃所有 `status: in_progress` task 的 `affected_files`
- 重疊 → **不認領**,改挑下一個
- orchestrator 拆解時應已序列化;若仍重疊 → 視為拆解錯誤,worker 寫 `fixed.md` 回報

## merge conflict 流程

執行中發生 git merge conflict:
1. worker 停手,**禁**強推
2. 寫 `fixed.md`:根因 = 拆解粒度問題 / `affected_files` 漏標
3. 通知 orchestrator 重拆(orchestrator 改 task 拆分,bump task 編號)

## 進度同步

| 層級 | 真相位置 |
| --- | --- |
| 版本進度 | `tasks-v{X.Y.Z}.md` 頂部狀態行 |
| Task 狀態 | `tasks/task-NNN-*.md` frontmatter `status:` |
| commit 對應 | commit message `[task-NNN]` tag |

## Worker 退場

- task `status: done` + Acceptance 全綠 → worker 釋出該 task
- task `blocked`(依賴未完 / 規範衝突)→ worker 標記後切換其他 task

## Orchestrator 收口

全部 task `done` 後 orchestrator 跑:
1. `/scan-project` — 全域檢測(對齊 `99-code-review/00-overview.md` acceptance gate)
2. P0 / P1 issue 存在 → 拆補洞 task,workers 再戰
3. 全綠 → `/reflect-rules` 升規候選
4. 開 PR,等 review

## 多 IDE / 多 model 並行

- Worker 可由不同工具(Claude / Codex / Cursor)擔任 — 規範跨工具一致(`AGENTS.md`)
- 認領協議走檔案系統(`status:` 欄位)+ git lock,**不**依賴單一 IDE
