-- verify_target_db.sql — 端到端驗證(唯讀)
--
-- 用途:兩支 Glue Job(ds_migrate / m2201)各跑一次成功後,連上目標 DB
--       erp_etl_hub_test 驗證:
--         (1) DS 搬移 / M2201 產生的目標表存在且筆數 > 0;
--         (2) 目標表每一欄位皆有 Comment(缺 Comment 欄位數應為 0)。
--
-- 安全規則(CLAUDE.md 毀滅性操作禁止 / 04-databases/04-sql-safety.md):
--   本檔**全部為 SELECT**,無任何 DDL / DML(無 CREATE/INSERT/UPDATE/DELETE/DROP/ALTER)。
--
-- 執行方式(Git Bash,連上目標 DB erp_etl_hub_test):
--   psql "postgresql://<user>:<pwd>@<host>:<port>/erp_etl_hub_test" -f etl/scripts/verify_target_db.sql
--   (或 psql -h <host> -U <user> -d erp_etl_hub_test -f etl/scripts/verify_target_db.sql)
--
-- 涵蓋範圍(對齊 mapping/ds.yaml 與 mapping/m2201.yaml):
--   schema DS     : GAT_FILE / GAQ_FILE / GAM_FILE
--   schema M2201  : M2201

\echo '========== [1] 目標表存在性與筆數(預期每列 row_count > 0) =========='

-- 逐表查 count(*):regclass 轉換若表不存在會報錯,故先確認表都建好。
-- 以 UNION ALL 彙整四張目標表的筆數,一眼看出是否有筆數為 0 的表。
SELECT 'DS.GAT_FILE'     AS target_table, count(*) AS row_count FROM "DS"."GAT_FILE"
UNION ALL
SELECT 'DS.GAQ_FILE'     AS target_table, count(*) AS row_count FROM "DS"."GAQ_FILE"
UNION ALL
SELECT 'DS.GAM_FILE'     AS target_table, count(*) AS row_count FROM "DS"."GAM_FILE"
UNION ALL
SELECT 'M2201.M2201'     AS target_table, count(*) AS row_count FROM "M2201"."M2201"
ORDER BY target_table;

\echo ''
\echo '========== [2] 筆數為 0 的目標表(預期 0 列;若有列即代表該表空) =========='

-- 把上面的筆數包成子查詢,只留下 row_count = 0 的表。理想結果:0 列。
SELECT target_table, row_count
FROM (
    SELECT 'DS.GAT_FILE' AS target_table, count(*) AS row_count FROM "DS"."GAT_FILE"
    UNION ALL
    SELECT 'DS.GAQ_FILE',                 count(*)               FROM "DS"."GAQ_FILE"
    UNION ALL
    SELECT 'DS.GAM_FILE',                 count(*)               FROM "DS"."GAM_FILE"
    UNION ALL
    SELECT 'M2201.M2201',                 count(*)               FROM "M2201"."M2201"
) AS t
WHERE row_count = 0
ORDER BY target_table;

\echo ''
\echo '========== [3] 每一欄位的 Comment(逐欄列出,comment 應皆非空) =========='

-- 以 information_schema.columns 取欄位清單,join pg_catalog 取欄位 Comment。
--   pg_class     : 表 → oid(relkind = r 一般表)
--   pg_namespace : schema 名
--   pg_attribute : 欄位 → attnum(ordinal_position)
--   pg_description: 欄位 Comment(objoid = 表 oid,objsubid = 欄位 attnum)
-- 僅看目標 schema(DS / M2201)的目標表。
SELECT
    c.table_schema,
    c.table_name,
    c.column_name,
    c.ordinal_position,
    col_description(pgc.oid, c.ordinal_position::int) AS column_comment
FROM information_schema.columns AS c
JOIN pg_catalog.pg_class     AS pgc ON pgc.relname = c.table_name
JOIN pg_catalog.pg_namespace AS pgn ON pgn.oid = pgc.relnamespace
                                    AND pgn.nspname = c.table_schema
WHERE c.table_schema IN ('DS', 'M2201')
  AND c.table_name   IN ('GAT_FILE', 'GAQ_FILE', 'GAM_FILE', 'M2201')
ORDER BY c.table_schema, c.table_name, c.ordinal_position;

\echo ''
\echo '========== [4] 缺 Comment 的欄位(理想結果 = 0 列) =========='

-- 同 [3] 的 join,但只留下 col_description 為 NULL 的欄位。
--   驗收標準:此查詢應回 0 列(代表每一欄位皆有 Comment)。
SELECT
    c.table_schema,
    c.table_name,
    c.column_name,
    c.ordinal_position
FROM information_schema.columns AS c
JOIN pg_catalog.pg_class     AS pgc ON pgc.relname = c.table_name
JOIN pg_catalog.pg_namespace AS pgn ON pgn.oid = pgc.relnamespace
                                    AND pgn.nspname = c.table_schema
WHERE c.table_schema IN ('DS', 'M2201')
  AND c.table_name   IN ('GAT_FILE', 'GAQ_FILE', 'GAM_FILE', 'M2201')
  AND col_description(pgc.oid, c.ordinal_position::int) IS NULL
ORDER BY c.table_schema, c.table_name, c.ordinal_position;

\echo ''
\echo '========== [5] 缺 Comment 欄位總數(理想 missing_comment_count = 0) =========='

-- 把 [4] 收斂成單一數字,方便自動化判讀(0 = 通過)。
SELECT count(*) AS missing_comment_count
FROM information_schema.columns AS c
JOIN pg_catalog.pg_class     AS pgc ON pgc.relname = c.table_name
JOIN pg_catalog.pg_namespace AS pgn ON pgn.oid = pgc.relnamespace
                                    AND pgn.nspname = c.table_schema
WHERE c.table_schema IN ('DS', 'M2201')
  AND c.table_name   IN ('GAT_FILE', 'GAQ_FILE', 'GAM_FILE', 'M2201')
  AND col_description(pgc.oid, c.ordinal_position::int) IS NULL;
