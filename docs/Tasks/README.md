# Tasks — 版本實作真相

> **本資料夾用途**:每個版本的**實作真相**(propose / tasks / fixed / reflect / scan)。**不**寫規範(屬於 `docs/Design-Base/`),**不**寫長期架構(屬於 `docs/Arch/`)。
>
> **規則優先序**:`docs/Design-Base/* > docs/Arch/* > AGENTS.md / CLAUDE.md > docs/Tasks/*`(本資料夾**最低**;可隨版本調整)
>
> **格式來源**:本資料夾的所有檔案格式定義於 `docs/Design-Base/01-propose/*` 與 `docs/Design-Base/99-code-review/01-fixed-md.md`。本檔僅作**目錄索引**。

---

## 結構

```
docs/Tasks/
├── README.md                                    # 本檔
├── v1.0.0/                                      # 版本資料夾(3-digit semver)
│   ├── propose-v1.0.0.md                        # User 寫:版本目標
│   ├── tasks-v1.0.0.md                          # Agent 拆:執行單元清單
│   ├── tasks/                                   # 細分子任務(可選,multi-agent 用)
│   │   ├── task-001-<slug>.md
│   │   ├── task-002-<slug>.md
│   │   └── ...
│   └── fixed.md                                 # 違規 / bug 根因(本版累積)
├── v1.1.0/
│   ├── propose-v1.1.0.md
│   ├── tasks-v1.1.0.md
│   ├── tasks/
│   └── fixed.md
├── v2.0.0/
│   └── ...
├── reflect/                                     # /reflect-rules 報告
│   ├── reflect-report-{YYMMDDHHMMSS}.md
│   └── ...
└── scan-project/                                # /scan-project 累積報告
    ├── 2026-05-07-1423.md
    └── ...
```

---

## 各檔對應規範

| 檔 | 由誰寫 | 格式定義 |
| --- | --- | --- |
| `propose-v{X.Y.Z}.md` | **User** | `docs/Design-Base/01-propose/01-propose-format.md` |
| `tasks-v{X.Y.Z}.md` + `tasks/task-NNN-*.md` | **Agent**(orchestrator) | `docs/Design-Base/01-propose/02-task-decomposition.md` |
| `fixed.md` | Agent(違規當下) | `docs/Design-Base/01-propose/04-fixed-format.md` + `docs/Design-Base/99-code-review/01-fixed-md.md` |
| `reflect/reflect-report-*.md` | `/reflect-rules` agent | `docs/Design-Base/01-propose/07-rule-evolution.md` |
| `scan-project/*.md` | `/scan-project` agent | `Harness-Engineering/prompts/scan-project.md` |
| `CHANGELOG.md`(repo 根目錄,非本資料夾) | Agent / User(release 前) | `docs/Design-Base/01-propose/06-changelog.md` |

---

## 何時讀

| 任務 | 讀哪 |
| --- | --- |
| 啟動新版本 | 開新 `v{X.Y.Z}/` 資料夾 + 寫 `propose-v{X.Y.Z}.md`(格式見 `01-propose/01-propose-format.md`) |
| Orchestrator 拆 task | 讀**當版** `propose-v{X.Y.Z}.md`,**不**預載歷史版本 |
| Worker 認領 task | 讀**當版** `tasks-v{X.Y.Z}.md` + `tasks/task-NNN-*.md`;依該 task `## 必讀檔` 載入 `docs/Design-Base/*` |
| 寫 fixed | 寫**當版** `fixed.md`(`01-propose/04-fixed-format.md`) |
| 跑 `/reflect-rules` | 讀**全版本** `v*/fixed.md`(找 pattern)→ 產出 `reflect/reflect-report-*.md` |
| 跑 `/scan-project` | 累積寫入 `scan-project/{YYYY-MM-DD}-{HHMM}.md` |

---

## 禁預載

下列檔案**不**預載到任何任務(Just-in-time loading 原則):

- 歷史版本的 `tasks-v*.md` / `fixed.md`(只讀當版)
- `reflect/reflect-report-*.md`(只在 `/reflect-rules` 任務讀)
- `scan-project/*.md`(只在 `/scan-project` 任務讀)

例外:`/reflect-rules` 必須讀**全版本** `v*/fixed.md`(本身就是跨版本分析任務)。

---

## 版本命名

- 採 **3-digit semver**:`v{MAJOR}.{MINOR}.{PATCH}`(例 `v1.0.0` / `v1.1.0` / `v2.0.0`)
- 判準:`docs/Design-Base/01-propose/05-version-bump.md`
- patch **不**獨立資料夾,patch 的 fix 寫進**該 minor 的 anchor 資料夾**(例:`v1.0.1` → `v1.0.0/fixed.md`)
- propose 對應 minor / major,patch 槽位寫 `0`(`propose-v1.0.0.md` / `propose-v1.1.0.md`)

---

## 跨版本累積

- `fixed.md` **屬當版**;不複製到下版本
- `reflect-report-*.md`、`scan-project/*.md` 累積式;**禁**刪除舊報告(歷史不可竄改)
- 棄用條目 → 加 `> 後續:已棄用,見 v{X.Y.Z} §M`,**不**直接移除

---

## 採用方專案啟動

新專案複製本 Harness-Engineering 時:

```bash
mkdir -p docs/Tasks/v1.0.0/tasks
mkdir -p docs/Tasks/reflect
mkdir -p docs/Tasks/scan-project
touch docs/Tasks/v1.0.0/propose-v1.0.0.md   # User 填
touch docs/Tasks/v1.0.0/tasks-v1.0.0.md     # 待 orchestrator 產
touch docs/Tasks/v1.0.0/fixed.md            # 待 agent 累積
```

User 接手寫 `propose-v1.0.0.md`(`docs/Design-Base/01-propose/01-propose-format.md`)→ orchestrator 拆 tasks → workers 並行執行。
