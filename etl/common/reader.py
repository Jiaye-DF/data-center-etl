"""來源讀取:以 Spark JDBC 從來源 RDS PostgreSQL erp_migration_test 讀取指定 schema 的表。

連線資訊(host / port / db / user / password)一律從 env 取,禁硬編字面值
(見 docs/Design-Base/00-overview/02-secrets.md)。本模組只負責讀取,不含轉換邏輯。

schema / table 名稱不字串直接拼進 SQL:先以白名單正則驗證,再以 PostgreSQL 雙引號
識別字引號化(見 docs/Design-Base/04-databases/04-sql-safety.md)。
"""

from __future__ import annotations

import os
import re
from typing import Any

try:  # Glue 上以 common.* 執行;fallback 供 repo 根以 etl.common.* 匯入
    from common.logger import get_logger, log_event
except ImportError:  # pragma: no cover
    from etl.common.logger import get_logger, log_event

# 合法識別字:字母或底線開頭,後接字母 / 數字 / 底線;排除 ; 空白 引號 -- 等注入字元
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# 允許讀取的 schema 白名單(來源 DB erp_migration_test)
_ALLOWED_SCHEMAS = frozenset({"DS", "M2201"})

_JDBC_DRIVER = "org.postgresql.Driver"


def quote_identifier(name: str) -> str:
    """驗證並引號化單一 PostgreSQL 識別字。

    僅接受符合 ``^[A-Za-z_][A-Za-z0-9_]*$`` 的名稱;非法名稱(含 ; 空白 引號 --)raise。
    通過後以雙引號包住,並將內含的 `"` 跳脫為 `""`(白名單已排除,屬雙重保險)。
    """
    if not isinstance(name, str) or not _IDENT_RE.match(name):
        raise ValueError(f"非法識別字:{name!r}")
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def qualified_table(schema: str, table: str) -> str:
    """組出已引號化的 "schema"."table",schema 須在白名單內。"""
    if schema not in _ALLOWED_SCHEMAS:
        raise ValueError(f"schema 不在白名單:{schema!r};允許:{sorted(_ALLOWED_SCHEMAS)}")
    return f"{quote_identifier(schema)}.{quote_identifier(table)}"


def build_jdbc_url() -> str:
    """由 env 組出來源 PostgreSQL 的 JDBC URL:jdbc:postgresql://host:port/db。

    需要 SOURCE_DB_HOST / SOURCE_DB_PORT / SOURCE_DB_NAME;缺任一 raise。
    """
    host = os.environ.get("SOURCE_DB_HOST")
    port = os.environ.get("SOURCE_DB_PORT")
    db = os.environ.get("SOURCE_DB_NAME")
    missing = [
        k
        for k, v in (("SOURCE_DB_HOST", host), ("SOURCE_DB_PORT", port), ("SOURCE_DB_NAME", db))
        if not v
    ]
    if missing:
        raise ValueError(f"缺少來源 DB 連線 env:{missing}")
    return f"jdbc:postgresql://{host}:{port}/{db}"


def _jdbc_credentials() -> tuple[str, str]:
    """從 env 取 user / password;缺任一 raise。回傳值禁進 log。"""
    user = os.environ.get("SOURCE_DB_USER")
    password = os.environ.get("SOURCE_DB_PASSWORD")
    missing = [
        k for k, v in (("SOURCE_DB_USER", user), ("SOURCE_DB_PASSWORD", password)) if not v
    ]
    if missing:
        raise ValueError(f"缺少來源 DB 憑證 env:{missing}")
    return user, password  # type: ignore[return-value]


# JDBC 讀取預設 fetchsize:PostgreSQL driver 預設逐批很小,大表逐列往返極慢
_DEFAULT_FETCHSIZE = 10_000

# partition 設定必備鍵(mapping yaml 的 tables.<表>.partition 區塊)
_PARTITION_REQUIRED_KEYS = ("column", "num_partitions", "lower_bound", "upper_bound")


def partition_options(partition: dict[str, Any] | None) -> dict[str, str]:
    """把 yaml 的 partition 區塊轉為 Spark JDBC 分區選項;None 回傳空 dict。

    需求鍵:column / num_partitions / lower_bound / upper_bound(缺任一 raise,
    不靜默退回單連線 — 設了一半代表 yaml 寫錯)。column 經識別字白名單驗證。
    """
    if partition is None:
        return {}
    missing = [k for k in _PARTITION_REQUIRED_KEYS if partition.get(k) is None]
    if missing:
        raise ValueError(f"partition 設定缺少必要鍵:{missing};需求:{list(_PARTITION_REQUIRED_KEYS)}")
    column = str(partition["column"])
    if not _IDENT_RE.match(column):
        raise ValueError(f"非法 partition column:{column!r}")
    return {
        "partitionColumn": column,
        "numPartitions": str(int(partition["num_partitions"])),
        "lowerBound": str(partition["lower_bound"]),
        "upperBound": str(partition["upper_bound"]),
    }


def read_table(
    spark: Any,
    schema: str,
    table: str,
    *,
    fetchsize: int = _DEFAULT_FETCHSIZE,
    partition: dict[str, Any] | None = None,
) -> Any:
    """以 Spark JDBC 從來源 erp_migration_test 讀 schema.table,回傳 Spark DataFrame。

    schema 須在白名單({DS, M2201});schema / table 經識別字引號化後作為 dbtable,
    不可注入。連線資訊全數來自 env(見 build_jdbc_url / _jdbc_credentials)。

    效能:
    - fetchsize 控制 driver 逐批抓取列數(預設 10000)。
    - partition 給定時以 partitionColumn 切 numPartitions 個並行連線讀取
      (大表必設;鍵見 partition_options docstring,通常放在 mapping yaml 的表定義)。
    """
    dbtable = qualified_table(schema, table)
    url = build_jdbc_url()
    user, password = _jdbc_credentials()
    part_opts = partition_options(partition)

    logger = get_logger("etl.reader")
    # 只 log schema / table / 分區數,禁 log URL / user / password
    log_event(
        logger,
        "讀取來源表",
        table=f"{schema}.{table}",
        partitions=part_opts.get("numPartitions", "1"),
    )

    reader = (
        spark.read.format("jdbc")
        .option("url", url)
        .option("driver", _JDBC_DRIVER)
        .option("dbtable", dbtable)
        .option("user", user)
        .option("password", password)
        .option("fetchsize", str(int(fetchsize)))
    )
    for key, value in part_opts.items():
        reader = reader.option(key, value)
    return reader.load()
