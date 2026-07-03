"""目標端寫入:把 DataFrame 落地到 erp_etl_hub_test,並套用欄位 Comment。

- 寫入走 Spark JDBC(pyspark 於函式內 import,py_compile / 匯入 ddl 時不需 pyspark)。
- 寫入後對目標 DB 執行 ddl.build_column_comments 產出的 COMMENT ON COLUMN。
- 目標 DB 連線一律走 env,禁硬編;禁 log 完整 connection string / password
  (見 docs/Design-Base/00-overview/02-secrets.md)。
"""

from __future__ import annotations

import os
from typing import Any

try:  # Glue 上以 common.* 執行;fallback 供 repo 根以 etl.common.* 匯入
    from common.ddl import build_column_comments, quote_ident
    from common.logger import get_logger, log_event
except ImportError:  # pragma: no cover
    from etl.common.ddl import build_column_comments, quote_ident
    from etl.common.logger import get_logger, log_event

_logger = get_logger("etl.writer")

# 目標 DB(erp_etl_hub_test)連線 env 變數名
_ENV_HOST = "TARGET_DB_HOST"
_ENV_PORT = "TARGET_DB_PORT"
_ENV_NAME = "TARGET_DB_NAME"
_ENV_USER = "TARGET_DB_USER"
_ENV_PASSWORD = "TARGET_DB_PASSWORD"


def _require_env(key: str) -> str:
    """讀取必要 env,缺少即 fail-fast(不印值)。"""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"缺少必要環境變數:{key}")
    return value


def target_conn_params() -> dict[str, str]:
    """從 env 組出目標 DB 連線參數。password 僅回傳、禁 log。"""
    return {
        "host": _require_env(_ENV_HOST),
        "port": os.environ.get(_ENV_PORT, "5432"),
        "database": _require_env(_ENV_NAME),
        "user": _require_env(_ENV_USER),
        "password": _require_env(_ENV_PASSWORD),
    }


def _jdbc_url(params: dict[str, str]) -> str:
    """組 PostgreSQL JDBC URL(不含帳密;帳密走 properties)。"""
    return f"jdbc:postgresql://{params['host']}:{params['port']}/{params['database']}"


# JDBC 批次寫入預設值:batchsize 控制單批 INSERT 列數;
# reWriteBatchedInserts 讓 PostgreSQL driver 把批次改寫為 multi-values INSERT(吞吐差距可達一個量級)
_DEFAULT_BATCHSIZE = 10_000


def write_table(
    df: Any,
    schema: str,
    table: str,
    comments: dict[str, str],
    *,
    mode: str = "overwrite",
    batchsize: int = _DEFAULT_BATCHSIZE,
) -> None:
    """把 DataFrame 落地到 erp_etl_hub_test.<schema>.<table>,寫入後套用欄位 Comment。

    - 表名沿用原始 table_name;欄位清單取自 df.columns。
    - comments 須涵蓋每一欄位,缺描述由 ddl.build_column_comments raise(不靜默略過)。
    - 目標連線走 env(TARGET_DB_*)。
    - 寫入以 batchsize 分批 + reWriteBatchedInserts=true(PostgreSQL 批次寫入最佳化)。
    """
    params = target_conn_params()
    url = _jdbc_url(params)
    columns = list(df.columns)

    # 先驗 comment 完整性(缺欄即 raise),避免寫入後才失敗
    comment_stmts = build_column_comments(table, columns, comments, schema=schema)

    props = {
        "user": params["user"],
        "password": params["password"],
        "driver": "org.postgresql.Driver",
    }
    dbtable = f"{quote_ident(schema)}.{quote_ident(table)}"
    df.write.format("jdbc").option("url", url).option("dbtable", dbtable).option(
        "user", props["user"]
    ).option("password", props["password"]).option("driver", props["driver"]).option(
        "batchsize", str(int(batchsize))
    ).option("reWriteBatchedInserts", "true").mode(mode).save()

    _apply_comments(url, params, comment_stmts)
    log_event(_logger, "目標表寫入完成並套用欄位 Comment", table=table, rows=len(columns))


def _apply_comments(url: str, params: dict[str, str], statements: list[str]) -> None:
    """對目標 DB 逐條執行 COMMENT ON COLUMN。透過 JVM JDBC(py4j),不另裝 driver。"""
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    gateway = spark.sparkContext._gateway
    jvm = gateway.jvm

    conn = jvm.java.sql.DriverManager.getConnection(url, params["user"], params["password"])
    try:
        stmt = conn.createStatement()
        try:
            for sql in statements:
                stmt.execute(sql)
        finally:
            stmt.close()
    finally:
        conn.close()
