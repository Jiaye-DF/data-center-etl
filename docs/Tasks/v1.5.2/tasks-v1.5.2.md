# Tasks v1.5.2

> 狀態:待認領(0/4;user 批准後 worker 才認領)

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | 同步 schema drift 偵測 + 目標表自動 ADD COLUMN | done | ✓ | — | `backend/app/etl/mirror.py` / `backend/tests/test_mirror.py` |
| 002 | 語意映射自動補列模組(confirmed + 表層級 + 別名查重 + DS 字典 zh) | done | ✓ | — | `backend/app/etl/semantic_autofill.py` / `backend/tests/test_semantic_autofill.py` |
| 003 | 同步收尾掛接:autofill → 副本重灌 → view 重生同輪生效 | done | ✗ | 002 | `backend/app/worker/tasks.py` / `backend/tests/test_semantic_mapping_sync.py` |
| 004 | e2e 驗證 + 收口文件 | pending | ✗ | 001, 002, 003 | `docs/Tasks/v1.5.2/verification-v1.5.2.md` |

## 拆解摘要

- **總量**:4 個 task,預估 ~11 hr。
- **並行**:001 / 002 影響檔案不重疊,可同時起跑;003 呼叫 002 產出的模組 → depends 002;004 收尾。
- **關鍵路徑**:`002 → 003 → 004`(~8 hr);001 為旁路可並行消化(003 的 e2e 語意仰賴 001,但程式碼無共檔,001 只需在 004 前完成)。
- **同檔互鎖**:無重疊(001 只動 `mirror.py`;003 只動 `worker/tasks.py`;002 全新檔)。
- **In Scope 對映**(無 orphan):drift 偵測 + ADD COLUMN → 001;映射自動補列 + 表層級 + 別名查重 → 002;同輪生效 → 003;驗收 → 004。
- **阻塞點**:003 是唯一動 `worker/tasks.py` 的 task;004 需可連目標 RDS 的環境做整合驗證。
- **派工建議**(model 分級,保守取高):001 opus·high / 002 opus·high / 003 opus·medium / 004 sonnet·medium。

## 執行前置(worker 認領前必讀)

- **分支**:`dev-v1.5.2/schema-drift`(自 main 982ed7b 切出)。
- **跑法**:改碼後以 `docker compose up -d --build` 驗證,**禁** start-dev。
- **底線**:全程只允許 `ADD COLUMN` / `INSERT`;禁任何 DROP / 欄位移除 / 改型別既有欄位。
- 協議:認領 task 改 `status: in_progress` + 註記 worker;Acceptance 全過才標 done;commit 帶 `[task-NNN]`。
- 全數 done 後:`/scan-project` → 修 → `/reflect-rules` → 收口。
