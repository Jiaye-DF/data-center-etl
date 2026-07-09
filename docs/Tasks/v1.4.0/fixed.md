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
