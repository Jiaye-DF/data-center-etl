---
id: task-006
title: S3 部署 + Glue Job 建置 + 端到端執行驗證
status: code-done-deploy-pending
parallel: false
depends_on: [task-004, task-005]
affected_files:
  - etl/scripts/deploy_s3.sh
  - etl/scripts/verify_target_db.sql
  - etl/README.md
estimated_hours: 3
---

## 目標

把 `etl/` 腳本部署到 S3、建立 / 設定 AWS Glue Job,並實際各執行一次 DS 搬移與 M2201 對應 job,驗證 propose 驗收標準:「Glue Job 可從 S3 讀取 `main.py` 成功執行一次」「`erp_etl_hub_test` 含由 DS 搬移的資料」「目標表每一欄位皆有 Comment」。此 task 是版本驗收的收口,001–005 全綠後才可認領。

## 範圍要點

- `scripts/deploy_s3.sh`:以 `aws s3 sync` 上傳 `etl/`(排除 `tests/`)至 `s3://$ETL_BUCKET/` 指定 prefix;bucket / prefix 由 env 注入,**禁**硬編(對齊 `00-overview/02-secrets.md`)。
- Glue Job 建立可用 AWS Console 或 `aws glue create-job`;若走 Console,操作步驟記錄於 `etl/README.md` 部署章節(script location 指向 S3 上的 `main.py`、`--additional-python-modules` / `--extra-py-files` 設定)。
- Glue connection / JDBC 憑證走 AWS 端設定(Glue Connection / Secrets Manager),**禁**寫進 repo。
- `scripts/verify_target_db.sql`:查詢目標 DB 驗證用 SQL(DS 表筆數 > 0、`pg_description` 每欄位 Comment 非空),唯讀查詢,**無**任何 DDL / DML。
- 本 task 只做部署 + 執行 + 驗證,**不改** 001–005 產出的程式碼;執行發現 bug 回寫對應 task 並記 `fixed.md`。

## Acceptance

> 以下 `aws` / `psql` 指令於 Git Bash 執行,`$ETL_BUCKET` / `$GLUE_JOB_NAME` / 目標 DB 連線由 env 注入。

- [ ] `aws s3 ls s3://$ETL_BUCKET/ --recursive | grep -q "main.py"`(腳本已上傳 S3)
- [ ] `aws glue get-job --job-name "$GLUE_JOB_NAME"` 成功(exit 0,Glue Job 存在且 script location 指向 S3)
- [ ] DS 搬移 job:`aws glue start-job-run` 後 `aws glue get-job-run` 之 `JobRunState` 為 `SUCCEEDED`
- [ ] M2201 對應 job:同上,`JobRunState` 為 `SUCCEEDED`
- [ ] `psql <目標DB> -f etl/scripts/verify_target_db.sql`:DS 來源表於 `erp_etl_hub_test` 皆存在且筆數 > 0
- [ ] 同上 SQL:`pg_description` 驗證目標表**每一欄位** Comment 非空(缺 Comment 欄位數 = 0)
- [ ] `git diff --stat` 不含 `backend/` `frontend/` 路徑(對齊 propose 驗收)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/02-secrets.md`(bucket / 憑證以 env 注入,禁硬編)
- `docs/Design-Base/00-overview/03-env-layers.md`(localhost ≠ 部署環境)
- `docs/Design-Base/04-databases/04-sql-safety.md`(驗證 SQL 唯讀、識別字安全)
