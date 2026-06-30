# CLAUDE.md

Claude Code 在 **Next.js (App Router) + TypeScript + FastAPI + PostgreSQL** 專案的全局規則,**本地開發優先**。具體規範見 `docs/Design-Base/`。

## 鎖定技術棧

- **Frontend**:Next.js 16 (App Router) + **TypeScript**(`strict: true`,**禁** `any`)
- **Backend**:FastAPI(Python)
- **Database**:PostgreSQL

不在此清單的棧 → 用其他 template,本模板**不適用**。任務涉及的框架 / 套件若不在 design-base 規範內,先告知使用者並暫停;**禁**自行擴張技術棧。

## 核心原則

- **輸出語言**:繁體中文(回應 / 註解 / 文件 / commit message)
- 簡潔:不主動建檔、不過度抽象、不預先設計未存在需求
- 不主動加註解(只在 *why* 從程式碼難推斷時加)
- 遵循既有風格,不擅自重構無關區塊
- 時區 / 機密 / 版本鎖定 / API 文件路徑等共通底線見 `docs/Design-Base/00-overview/`(以該層為準)
- **本地開發優先**:後端 dev server + 前端 dev server;依賴服務由開發者於本機 install

## 毀滅性操作禁止

- **禁止任何 DROP 類資料庫操作**:不得執行、產生或建議 `DROP DATABASE` / `DROP SCHEMA` / `DROP TABLE` / `DROP COLUMN` 等會刪除資料或結構的 SQL / migration。
- **禁止刪除 Docker volume**:不得執行、產生或建議 `docker-compose down -v`、`docker compose down -v`、`--volumes` 等會移除 volume 的操作。
- **禁止使用 `rm -rf`**:不得在 shell、script、文件或自動化流程中使用 `rm -rf` 或等價的強制遞迴刪除操作。
- 任何可能造成資料遺失、不可逆清除、volume 消失、環境重建的指令,必須停下來改用安全替代方案,或請人類負責人手動確認與備份後處理。

## localhost ≠ 部署環境

- `.env.development` 出現的 `localhost:*` 是**本地開發專用**;部署時必須改為實際 host
- **禁止**直接把 `.env.development` 拿去部署 — 會連不到依賴服務,且機密為 development 預設值會觸發 fail-fast
- 詳細環境分層 / Coolify 部署規範見 `docs/Design-Base/00-overview/03-env-layers.md` 與 `docs/Design-Base/06-Coolify-CD/`

## 任務前必讀

依任務性質載入 `docs/Design-Base/<area>/` 下相關 `*.md`(依 `AGENTS.md § Just-in-time Loading 對照表`);跨領域任務同時載入多個目錄。規則衝突依〈規範優先順序〉判定。任務中規範被推翻 → commit / task doc 註明,並提醒使用者更新規範檔。

## Git 工作流程

- 主分支 `main`,功能分支從 `main` 切出
- Commit message 繁中 `(AI?) <類型>: <描述>`(類型 `Add | Modify | Fix | Refactor | Docs`),AI 產生**必**前綴 `(AI)`
- 未經明示授權,**禁**破壞性操作(`--force` / `reset --hard` / `--no-verify`)
- 詳細格式 / fixed.md / PR self-check 見 `docs/Design-Base/99-code-review/`

## 規範優先順序

`docs/Design-Base/*` > `docs/Arch/*` > 本檔案 > `docs/Tasks/*`

- `docs/Design-Base/`:實作規範(程式碼風格、DB / API 規範、版本鎖定)— 底線
- `docs/Arch/`:長期架構方向
- `docs/Tasks/`:單版本構想 / 清單,可隨版本調整
