# 00-overview — 跨領域共通底線

跨專案最頂層規則,鎖定 **React + TypeScript + FastAPI + PostgreSQL**,本地開發優先。

> **任務 → 必讀檔對照**:`docs/Design-Base/README.md`(library API 索引);任何任務先讀該檔知道載哪些。

---

## 規範優先順序

`docs/Design-Base/* > docs/Arch/* > AGENTS.md / CLAUDE.md > docs/Tasks/*`

衝突依此優先序機械式判定。`AGENTS.md` 與 `CLAUDE.md` 同層,內容須一致;`CLAUDE.md` 僅補充 Claude 特性,不重述。

---

## 輸出語言 / 註解 / commit(永遠遵守)

- **輸出語言**:繁體中文(回應 / 註解 / 文件 / commit message)
- **Comments**:不主動加;只在 *why* 從程式碼難推斷時加
- **commit message**:繁中 `(AI?) <類型>: <描述>`,類型 `Add | Modify | Fix | Refactor | Docs`

詳細 commit 格式見 `99-code-review/02-commit-message.md`。

---

## 子章節

- `01-versions.md` — 版本鎖到 patch + Sources of Truth
- `02-secrets.md` — 機密 env 注入 + .gitignore + fail-fast
- `03-env-layers.md` — localhost vs 部署
- `04-api-docs.md` — `/api/docs` 規範
- `05-timezone.md` — UTC+8 全棧一致
