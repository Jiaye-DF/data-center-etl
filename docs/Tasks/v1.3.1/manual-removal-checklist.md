# v1.3.1 人工移除清單(待 DROP 的表 / 欄 + 備份指引)

> **本 repo 不提供 DROP migration。** 依 `CLAUDE.md`〈毀滅性操作禁止〉,本專案不執行、不產生、不建議任何 `DROP DATABASE` / `DROP SCHEMA` / `DROP TABLE` / `DROP COLUMN` 等會刪除資料或結構的 SQL / migration。
>
> 下列物件在 v1.3.1 已於**程式面下線**(移除引用),但**實體結構保留**。實際 DROP 為**人工、不可逆**操作,須由人類負責人於維護窗口手動執行並記錄。本文件僅提供「零引用檢查」與「備份指引」,文中任何 `DROP TABLE` / `DROP COLUMN` 皆為**人工待執行範例**,非 repo 自動化。

---

## 執行總則(每項共用)

依序執行,任一步未通過即中止,不得跳步:

1. **先備份** — `pg_dump` 目標表(或全庫),確認備份檔可用。
2. **確認程式面零引用** — 執行該項的「零引用檢查指令」,確定無命中(`.pyc` 等編譯快取不列入,以原始碼為準)。
3. **解除相依** — 若目標被 FK 參照,先解 FK 或先 DROP 依賴方(見各項相依提醒)。
4. **維護窗口手動執行** — 由負責人於維護時段手動執行 DROP,並在變更紀錄登載。

備份指引為**佔位**,實際連線參數(host / port / db / user)由負責人依部署環境填入;本機開發 DB 與部署 DB 連線不同,禁止把 `.env.development` 連線直接拿去部署庫操作。

```bash
# 通用備份佔位(負責人填入實際連線;-Fc = custom 格式,利於單表還原)
pg_dump -h <HOST> -p <PORT> -U <USER> -d <DB> -Fc -t <SCHEMA>.<TABLE> -f <TABLE>_backup_$(date +%Y%m%d).dump
# 或全庫備份
pg_dump -h <HOST> -p <PORT> -U <USER> -d <DB> -Fc -f <DB>_full_$(date +%Y%m%d).dump
```

---

## 相依關係總覽(DROP 順序關鍵)

`etl_tables.pid` 被以下 FK 參照,DROP `etl_tables` 前必須先處理**所有**參照方:

| 參照方(依賴方) | FK 欄 | FK 約束名 |
| --- | --- | --- |
| `etl_mappings` | `etl_table_pid` | `fk_etl_mappings_etl_table` |
| `etl_run_logs` | `etl_table_pid` | `fk_etl_run_logs_etl_table` |
| `schedules` | `etl_table_pid` | `fk_schedules_etl_table` |

> **DROP 順序**:先解各參照方的 FK 或先移除依賴方欄/表 → 最後才 DROP `etl_tables`。直接 DROP `etl_tables` 會因 FK 相依失敗。`etl_run_logs`(歷史執行紀錄)是否保留由負責人決定;若保留該表,至少須先 DROP 其 `etl_table_pid` 欄或解除 `fk_etl_run_logs_etl_table`。

---

## 1. `etl_tables`(表)

| 項目 | 內容 |
| --- | --- |
| 物件 / 型別 | `etl_tables` — 資料表 |
| 來源 | v1.1 config 驅動 ETL 的設定表 |
| 下線 task | task-006 / task-008(移除 config ETL 引擎與端點) |
| 相依 | 被 `etl_mappings` / `etl_run_logs` / `schedules` 三張表的 `etl_table_pid` FK 參照 |

**零引用檢查指令**(應無原始碼命中):

```bash
grep -rn "etl_tables" backend/app --include="*.py"
```

**備份指引**:

```bash
pg_dump -h <HOST> -p <PORT> -U <USER> -d <DB> -Fc -t public.etl_tables -f etl_tables_backup_$(date +%Y%m%d).dump
```

**人工待執行範例(手動,非 repo 自動化)**:

```sql
-- 手動:須在所有參照方(etl_mappings / etl_run_logs / schedules)之 FK 解除或依賴移除後才可執行
DROP TABLE public.etl_tables;
```

---

## 2. `etl_mappings`(表)

| 項目 | 內容 |
| --- | --- |
| 物件 / 型別 | `etl_mappings` — 資料表 |
| 來源 | v1.1 config 驅動 ETL 的欄位對照表 |
| 下線 task | task-006 / task-008(移除 config ETL 引擎與端點) |
| 相依 | 以 `etl_table_pid` FK(`fk_etl_mappings_etl_table`)參照 `etl_tables`;為 `etl_tables` 的依賴方,應先於或連同 `etl_tables` 移除 |

**零引用檢查指令**(應無原始碼命中):

```bash
grep -rn "etl_mappings\|EtlMapping" backend/app --include="*.py"
```

**備份指引**:

```bash
pg_dump -h <HOST> -p <PORT> -U <USER> -d <DB> -Fc -t public.etl_mappings -f etl_mappings_backup_$(date +%Y%m%d).dump
```

**人工待執行範例(手動,非 repo 自動化)**:

```sql
-- 手動:etl_mappings 為 etl_tables 的依賴方,DROP 本表可一併解除 fk_etl_mappings_etl_table
DROP TABLE public.etl_mappings;
```

---

## 3. `schedules.etl_table_pid`(欄)

| 項目 | 內容 |
| --- | --- |
| 物件 / 型別 | `schedules.etl_table_pid` — 資料表欄位 |
| 來源 | config ETL 排程綁定,deprecated |
| 下線 task | task-001 標記為 deprecated(停止讀寫) |
| 相依 | 該欄以 `fk_schedules_etl_table` FK 參照 `etl_tables.pid`;DROP 欄前須先解此 FK,且此欄的存在會阻擋 `etl_tables` 的 DROP |

**零引用檢查指令**(應無原始碼命中):

```bash
grep -rn "etl_table_pid" backend/app --include="*.py"
```

**備份指引**(僅移除單欄,建議先備份整表以利回復):

```bash
pg_dump -h <HOST> -p <PORT> -U <USER> -d <DB> -Fc -t public.schedules -f schedules_backup_$(date +%Y%m%d).dump
```

**人工待執行範例(手動,非 repo 自動化)**:

```sql
-- 手動:先解 FK,再 DROP 欄
ALTER TABLE public.schedules DROP CONSTRAINT fk_schedules_etl_table;
ALTER TABLE public.schedules DROP COLUMN etl_table_pid;
```

---

## 4. `rds_table_meta.sync_excluded`(欄)

| 項目 | 內容 |
| --- | --- |
| 物件 / 型別 | `rds_table_meta.sync_excluded` — 資料表欄位 |
| 來源 | v1.3.0 逐表排除同步旗標,已廢止 |
| 下線 task | task-005 停止讀取(逐表排除機制廢止) |
| 相依 | 無 FK 相依,可獨立移除 |

**零引用檢查指令**(應無原始碼命中):

```bash
grep -rn "sync_excluded" backend/app --include="*.py"
```

**備份指引**(僅移除單欄,建議先備份整表以利回復):

```bash
pg_dump -h <HOST> -p <PORT> -U <USER> -d <DB> -Fc -t public.rds_table_meta -f rds_table_meta_backup_$(date +%Y%m%d).dump
```

**人工待執行範例(手動,非 repo 自動化)**:

```sql
-- 手動:無 FK 相依,可直接 DROP 欄
ALTER TABLE public.rds_table_meta DROP COLUMN sync_excluded;
```

---

## 收尾檢查清單

- [ ] 四項各自的備份檔已產出且可還原
- [ ] 四項的零引用檢查指令均無原始碼命中
- [ ] `etl_tables` 的三個 FK 參照方(`etl_mappings` / `etl_run_logs` / `schedules`)已依序處理
- [ ] DROP 於維護窗口手動執行,並在變更紀錄登載執行人、時間、備份檔位置
- [ ] 確認 repo 未新增任何 DROP migration(符合 `CLAUDE.md`〈毀滅性操作禁止〉)
