---
name: stop-dev
description: 停止 scaffold 出來專案的 backend (uvicorn) + frontend (vite) dev server。kill 占用 backend_port / frontend_port 的 listener。當使用者說「停止專案 / 關掉 / 停 dev / stop dev / 關閉開發環境」時觸發。
---

# stop-dev

停掉本專案的 dev server。配對 `/start-dev` 使用。

## 心法

1. **Surgical**:只 kill `backend_port` / `frontend_port` 兩個 listener,不誤傷其他 process
2. **平台自適應**:Windows 用 PowerShell;macOS / Linux 用 bash
3. **冪等**:重複跑沒事(沒 process 就回報「未在跑」)

## 執行步驟

### 1. cwd 健全性檢查

確認當前目錄是 scaffold 出來的專案:`backend/pyproject.toml` + `frontend/package.json` 都存在。

不是 → 中止,告知使用者「請 cd 到專案根目錄再跑 `/stop-dev`」。

### 2. 讀取 port 設定

同 `/start-dev` § 2:優先 `<cwd>/.env` → `vite.config.ts` → 預設 8000 / 3000。

### 3. kill listener

#### Windows

```powershell
foreach ($port in @(<backend_port>, <frontend_port>)) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Host ":$port 未在跑"; continue }
    $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pid in $procIds) {
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) { Write-Host "kill PID $pid ($($proc.ProcessName)) 占用 :$port"; Stop-Process -Id $pid -Force }
    }
}
```

#### macOS / Linux

```bash
for port in <backend_port> <frontend_port>; do
    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)
    elif command -v fuser >/dev/null 2>&1; then
        pids=$(fuser -n tcp "$port" 2>/dev/null | tr -d ':/tcp' || true)
    fi
    if [ -z "$pids" ]; then echo ":$port 未在跑"; continue; fi
    for pid in $pids; do
        echo "kill PID $pid 占用 :$port"
        kill -9 "$pid" 2>/dev/null || true
    done
done
```

### 4. 報告

告訴使用者哪些 PID 被 kill、哪些 port 本來就沒 process。

## 自我約束

- **禁止**修改任何 source code / 設定檔
- **禁止**碰非本專案的兩個 port 的其他 process
- **禁止**對 cwd 不是 scaffold 出來的專案執行 kill(§ 1 擋住)
- **禁止**用「kill 全部 node / python」之類粗暴指令(會誤殺使用者其他開發 process)
