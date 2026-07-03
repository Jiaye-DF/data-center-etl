-- bootstrap_target_db.sql — 目標 DB erp_etl_hub_test 一次性建置
--
-- 用途:建立 ETL 落地目標的 database 與 schema。
-- 安全規則(CLAUDE.md 毀滅性操作禁止):本檔**只准 CREATE**,
--   嚴禁任何刪除類 DDL(移除 database / schema / table / column 的操作一律不得出現)。
--
-- 執行方式(以具建庫權限帳號連上 PostgreSQL,例:預設 postgres 庫):
--   psql -h <host> -U <admin_user> -f etl/scripts/bootstrap_target_db.sql
--
-- 注意:PostgreSQL 的 CREATE DATABASE 不支援 IF NOT EXISTS,
--   若目標庫已存在,執行此行會報「database already exists」— 屬預期,可略過該行續跑。

-- 1) 建立目標資料庫(若已存在,略過此行即可)
CREATE DATABASE erp_etl_hub_test
    ENCODING 'UTF8'
    LC_COLLATE 'C'
    LC_CTYPE 'C'
    TEMPLATE template0;

-- 2) 以下 schema 建置須先 \c erp_etl_hub_test 切入該庫再執行:
--   \c erp_etl_hub_test

-- 建立 ETL 落地用 schema(可重複執行,已存在則略)
CREATE SCHEMA IF NOT EXISTS etl;

-- public schema 一般預設已存在;此行為冪等保險,不刪不改既有物件
CREATE SCHEMA IF NOT EXISTS public;
