# fixed.md — v1.4.0

## 1. COMMENT 內容含冒號被 text() 誤判為 bind 參數,同步該表必失敗(既存自 v1.1.0)  〔2026-07-09 10:03:00〕

**問題**:同步 `DS.AZA_FILE` / `DS.MAJ_FILE` / `DS.SMA_FILE` 逐表 log 皆 failed,錯誤 `(sqlalchemy.exc.InvalidRequestError) A value is required for bind parameter '是' [SQL: COMMENT ON COLUMN "DS"."AZA_FILE"."AZA72" IS '是否與EasyFlowGP整合(''Y''$1, ''N''$2)';]`。

根因:COMMENT 語句由 `comments.quote_literal` 跳脫組裝成「成品 DDL 字串」後,執行時又包一層 `sqlalchemy.text(stmt)` 重新解析;`text()` 會把字串中 `:` 緊接文字的片段(如 `'Y':是`、`:1`)當作具名 bind 參數,找不到綁定值即 raise。埋於 v1.1.0 `writer.write_table`(config-driven 引擎)、v1.2.0 `mirror.write_mirror`(自動鏡像)沿用同寫法;先前未暴露是因為字典描述都不含「冒號緊接非空白文字」,直到 DS 字典出現 `('Y':是, 'N':否)` 這類描述才觸發。

**修正**:兩處執行點改 `conn.exec_driver_sql(stmt)` 直送 driver,跳過 `text()` 解析(COMMENT 為已跳脫完成之 DDL,無 bind 參數需求);新增回歸測試釘住「含冒號 COMMENT 必走 driver 直送且內容原樣」。已於 docker 環境對三張表實跑鏡像驗證:全部成功,目標欄 COMMENT 冒號內容原樣落地。

**影響檔案**:
- `backend/app/etl/mirror.py`
- `backend/app/etl/writer.py`
- `backend/tests/test_mirror.py`

## 2. 狀態膠囊(StatusBadge)在窄欄被折行擠壓變形(既存自 v1.1.0)  〔2026-07-09 09:55:00〕

**問題**:run 明細「逐表詳細 log」表格中,錯誤日誌欄內容很長時其他欄被壓縮,「失敗」等兩字膠囊折成兩行、圓角膠囊變形難讀。

根因:`.df-badge` 樣式自 v1.1.0 引入以來未設 `whitespace-nowrap`,表格欄寬被長內容擠壓時 CJK 文字在膠囊內換行;先前未暴露是因為逐表 log 少有長錯誤訊息同列並存的情境。

**修正**:1. `.df-badge` 加 `whitespace-nowrap`(全站膠囊一體受益);2. 逐表 log 表「狀態」欄表頭加 `min-w-[5.5rem]` 保留呼吸空間。

**影響檔案**:
- `frontend/src/app/globals.css`
- `frontend/src/components/runs/RunLogTable.tsx`

## 3. 多 worker 共用工作樹,worker 全域 git stash 清掉他人未提交工作(流程事故)  〔2026-07-09 12:10:00〕

- **時間**:2026-07-09T12:10+08:00
- **commit / PR**:無獨立 commit;相關 task commit `a3ee9ef`(task-001)、`8476381`(task-003 重做後成果)
- **影響檔案**:task-003 全部 WIP(六 router + 三測試檔,當時未提交)一度被清空;最終無損失(worker 重做)
- **問題**:v1.4.0 波次 A 三 worker 並行時,task-001 worker 為建立 mypy 乾淨基線,對**共用工作目錄**執行 `git stash --include-untracked`,連帶把 task-003 worker 的全部未提交變更掃進 stash;task-003 worker 發現所有編輯被還原為 HEAD,被迫全部重做。遺留混合快照 `stash@{0}: task-001-wip`(禁 pop,待 drop)。
- **根因**:多 worker 共用同一 working directory 時,`01-propose/03-multi-agent-flow.md` 的認領協議只互鎖「檔案白名單」層(affected_files 不重疊),**未禁止影響全工作樹的 git 操作**(stash / checkout -- . / reset),也未提供 worktree 隔離選項 — 白名單互鎖擋不住全域操作的波及。
- **修正**:orchestrator 當場改採「每 task 完成即刻 commit 保護」+ 後續派工單明令禁 stash;task-001 worker 自行以 `git checkout stash@{0} -- <own files>` 精準復原自己檔案、未動他人工作樹。
- **規範參照**:`01-propose/03-multi-agent-flow.md`(規則缺口:無工作樹紀律條款)
- **後續**:reflect 候選 — 新增「共用工作樹 git 紀律」(禁全域 stash/checkout/reset)+ worktree 隔離指引

## 4. RBAC 權限收緊屬 major 判準,user 裁定內部後台走 minor(規範被推翻)  〔2026-07-09 10:30:00〕

- **時間**:2026-07-09T10:30+08:00(propose 批准時裁定)
- **commit / PR**:`5ea863f`(propose 註記)、`8476381` / `9f03f4c`(實作)
- **影響檔案**:`docs/Tasks/v1.4.0/propose-v1.4.0.md § 風險`、backend 六 router、frontend 守衛
- **問題**:v1.4.0 RBAC 全面 admin-only 使 viewer 失去既有讀取權,依 `01-propose/05-version-bump.md`「權限收緊,既有 user 失去存取 → bump major」判準應發 v2.0.0,實際以 v1.4.0(minor)發布。
- **根因**:版本規則未區分「對外產品」與「公司內部後台」情境 — 內部後台受影響者(member/viewer)即權限收緊的目標對象,非契約破壞的受害者;一刀切 major 在內部工具上成本(major 心理門檻/溝通成本)大於效益。user 裁定推翻,已於 propose § 風險與變更紀錄註明,CHANGELOG 發布時標示權限變更。
- **修正**:無程式修正(屬版號決策);propose / tasks-v1.4.0.md 均已註記。
- **規範參照**:`01-propose/05-version-bump.md § breaking 判準`(被推翻)
- **後續**:reflect 候選 — 若此類例外要常態化,把「內部系統權限收緊可走 minor」寫進 05-version-bump.md(tasks-v1.4.0.md § 拆解摘要已明文提醒)

## 5. 並行 worker 共用單一測試 DB,pytest 間歇互踩(環境約定缺口)  〔2026-07-09 12:20:00〕

- **時間**:2026-07-09T12:20+08:00
- **commit / PR**:無(未改測試基建);全套最終於獨占環境驗證 `a3ee9ef` 前 214 passed
- **影響檔案**:`backend/tests/*`(執行期互踩,檔案本身無缺陷)
- **問題**:波次 A 兩個後端 worker 同時對同一測試 DB(localhost:5435)跑 `uv run pytest`,出現 FK 違反 / unique 衝突 / 密碼認證失敗等**間歇性**錯誤且每次失敗集合不同;單獨重跑均全綠。task-001 worker 因此無法在任務內觀測「完整套件全綠」,由 orchestrator 收口時獨占補跑。
- **根因**:`03-backend/07-testing.md` 過薄(前次 scan 第 7 章已點名),無「測試 DB 隔離 / 並行使用約定」— 測試檔以固定 DB 名 + 清表 fixture 設計,天然假設單一執行者;multi-agent 並行拆解時無規則要求後端 task 錯開測試或各用獨立 DB。
- **修正**:本次以流程繞開(orchestrator 序列化最終驗證);測試基建未改。
- **規範參照**:`03-backend/07-testing.md`(規則缺口)
- **後續**:reflect 候選 — 補「並行執行約定」(per-worker 測試 DB 名 env 化,或明定全套 pytest 屬收口獨占動作)
