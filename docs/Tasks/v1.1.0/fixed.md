# Fixed v1.1.0

> 本版所有規範違反 / bug 根因累積於此。條目格式見 `docs/Design-Base/01-propose/04-fixed-format.md`;§ 編號全版本連號,**禁**刪除舊條目。

## §1 — v1.1.0 新依賴已鎖版但 `01-versions.md` 套件清單未同步

- **時間**:2026-07-03T16:48+08:00
- **commit / PR**:task-001 commit(taskiq / taskiq-redis / pyyaml / pytest-asyncio / respx / types-pyyaml 鎖版)
- **影響檔案**:`backend/pyproject.toml`、`backend/uv.lock`、`docs/Design-Base/00-overview/01-versions.md`(未改)
- **問題**:task-001 依規新增 v1.1.0 後端依賴並全數鎖到 patch 版,但 `01-versions.md` 規定「加入時補進本表」;該檔屬 Design-Base,不在 task-001 `affected_files` 白名單,worker 依 multi-agent 硬約束不得修改,導致套件清單與 lock file 不一致
- **根因**:task 拆解時 `affected_files` 只涵蓋程式碼與 lock file,未把「新增依賴須同步 `01-versions.md` 套件清單」的規範義務納入任何 task 的影響檔案 → 規範義務與檔案白名單互斥
- **修正**:依賴照常鎖版(pyproject / uv.lock 已逐字一致);`01-versions.md` 補表留待收口(user 或收口 agent)處理。另註:pyproject 既有版本(fastapi 0.136.1 等)先前即高於該表 lock 範例,屬既存不一致,同樣待收口對表
- **規範參照**:`docs/Design-Base/00-overview/01-versions.md § 鎖定原則 / Sources of Truth`
- **後續**:收口時把 taskiq==0.12.4 / taskiq-redis==1.2.3 / pyyaml==6.0.3 / pytest-asyncio==1.4.0 / respx==0.23.1 / types-pyyaml==6.0.12.20260518 補進 `01-versions.md` 套件表,並以 lock 為準校正既存 lock 範例;reflect 候選 — 拆 task 時規範連動檔(版本表)應自動列入 affected_files
