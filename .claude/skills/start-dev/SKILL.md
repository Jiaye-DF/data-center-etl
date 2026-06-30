---
name: start-dev
description: 在 scaffold 出來的專案目錄啟動 backend (uvicorn) + frontend (vite) dev server。自動偵測 port 占用並 kill 舊 process,平台自適應(Windows / macOS / Linux)。當使用者說「啟動專案 / 跑起來 / 開發環境啟動 / start dev」時觸發。
---

# start-dev

啟動 backend + frontend dev server。重複跑會自動 kill 舊 process,不會卡死。

## 心法

1. **不改 source code**:本 skill 只啟停 process,不動任何檔案內容
2. **冪等**:重複跑會 kill 舊的再啟動,使用者不需先停再開
3. **平台自適應**:`process.platform` / `$IsWindows` / `uname` 決定用 PowerShell 還是 bash
4. **背景啟動**:使用 Bash tool `run_in_background: true`,讓使用者可以繼續操作 Claude Code

## 執行步驟

### 1. cwd 健全性檢查

確認當前目錄是 scaffold 出來的專案。檢查兩個檔案:

- `backend/pyproject.toml`(用 Read 或 ls 確認)
- `frontend/package.json`

任一不存在 → **中止**,告知使用者:「當前目錄不是 scaffold 出來的專案,請 `cd` 到專案根目錄(含 `backend/` 與 `frontend/` 兩個子目錄那層)後重新跑 `/start-dev`。」

### 2. 讀取 port 設定

預設:`backend_port=8000`、`frontend_port=3000`。

優先順序:
1. 若 `<cwd>/.env` 存在,grep `BACKEND_PORT` / `FRONTEND_PORT` 取值
2. 若 `<cwd>/frontend/vite.config.ts` 含 `port: <n>`,以該值為 frontend
3. 否則用預設 8000 / 3000

讀到後**回報**給使用者:`backend_port` / `frontend_port` 各是多少。

### 3. 偵測 port 占用 + kill

#### Windows(PowerShell)

```powershell
$port = <port>
$conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($conns) {
    $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pid in $procIds) {
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) { Write-Host "kill PID $pid ($($proc.ProcessName)) 占用 :$port"; Stop-Process -Id $pid -Force }
    }
} else { Write-Host ":$port 未被占用" }
```

#### macOS / Linux(bash)

```bash
port=<port>
if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)
elif command -v fuser >/dev/null 2>&1; then
    pids=$(fuser -n tcp "$port" 2>/dev/null | tr -d ':/tcp' || true)
fi
if [ -n "$pids" ]; then
    for pid in $pids; do
        echo "kill PID $pid 占用 :$port"
        kill -9 "$pid" 2>/dev/null || true
    done
else
    echo ":$port 未被占用"
fi
```

對 `backend_port` 與 `frontend_port` **各執行一次**。把 kill 結果列給使用者看(透明可審計)。

### 4. 啟動 dev server(背景)

#### Windows

各開新 PowerShell 視窗(讓 log 獨立、方便除錯):

```powershell
Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$PWD\backend'; uv run uvicorn app.main:app --reload --port <backend_port> --host 0.0.0.0"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$PWD\frontend'; npm run dev"
```

#### macOS / Linux

用 Bash tool 啟動兩個背景 process(`run_in_background: true`):

- backend:`cd backend && uv run uvicorn app.main:app --reload --port <backend_port> --host 0.0.0.0`
- frontend:`cd frontend && npm run dev`

**啟動後等 2–3 秒**,用 `curl -s -o /dev/null -w "%{http_code}" http://localhost:<port>/api/docs`(backend)與 `http://localhost:<frontend_port>`(frontend)做 smoke check;非 200 / 404 → 警示使用者啟動可能失敗,並貼最後幾行 log。

### 5. 報告

告訴使用者:
- Backend Swagger:`http://localhost:<backend_port>/api/docs`
- Backend Health :`http://localhost:<backend_port>/api/v1/health`
- Frontend       :`http://localhost:<frontend_port>`
- 停止方式:`/stop-dev`,或重跑 `/start-dev`(會自動 kill 舊的)

## 自我約束

- **禁止**修改任何 source code / 設定檔(`.env` / `pyproject.toml` / `package.json` / `vite.config.ts`)— 本 skill 只讀不寫
- **禁止**碰非 backend / frontend 兩個 port 的其他 process(別誤殺使用者其他開發環境)
- **禁止**在不是 scaffold 出來的專案目錄啟動(§ 1 健全性檢查擋住)
- **禁止**靜默成功 — 啟動後做 smoke check,任一失敗要告知使用者並貼錯誤訊息
- **禁止**改 `.env` 或修補 `BACKEND_PORT` / `FRONTEND_PORT`(只讀,不寫)
- 若使用者沒裝 `uv` 或 `npm`,告知使用者並中止(不要假裝可以跑)

## 不做的事

- 不跑 `uv sync` / `npm ci` / `alembic upgrade`(這些屬於「首次設定」,在 README.md 講)
- 不跑 acceptance test(`ruff` / `mypy` / `typecheck`)
- 不檢查 git 狀態
- 不啟 PostgreSQL(那是本機 service,使用者自己起)
