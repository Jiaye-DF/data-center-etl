"""DS schema 整份搬移 job。

流程(每張 yaml 定義的表):
  1. reader.read_table 從來源 erp_migration_test."DS".<table> 讀取。
  2. transforms/ds 依欄名做型別 / null 正規化。
  3. writer.write_table 寫入目標 erp_etl_hub_test.<table>,套用 config["mapping"]["ds"] 的欄位 Comment。

供 main.py 動態派工:提供 run(spark, config);本檔不改 main.py。
頂層僅 import 不需 pyspark 的模組(reader / writer / transforms 皆然),確保無 pyspark 時可 py_compile / import。
"""

from __future__ import annotations

from typing import Any

try:  # Glue 上以 common.* / transforms.* 執行;fallback 供 repo 根以 etl.* 匯入
    from common.logger import get_logger, log_event
    from common.reader import read_table
    from common.writer import write_table
except ImportError:  # pragma: no cover
    from etl.common.logger import get_logger, log_event
    from etl.common.reader import read_table
    from etl.common.writer import write_table

try:
    from transforms.ds import normalize_value
except ImportError:  # pragma: no cover
    from etl.transforms.ds import normalize_value

_SOURCE_SCHEMA = "DS"
_TARGET_SCHEMA = "DS"


def _table_columns(table_def: dict[str, Any]) -> list[str]:
    """取出該表 yaml 定義的欄位名清單(順序即 yaml 撰寫順序)。"""
    columns = table_def.get("columns")
    if not isinstance(columns, dict) or not columns:
        raise ValueError("ds.yaml 表定義缺少 columns 或為空")
    return list(columns.keys())


def _table_comments(table_def: dict[str, Any]) -> dict[str, str]:
    """把 yaml 的 columns.<欄>.comment 攤平為 {欄名: 描述}。"""
    return {col: spec["comment"] for col, spec in table_def["columns"].items()}


def _transform_df(df: Any, columns: list[str]) -> Any:
    """對 df 依 yaml 欄位清單做欄位級正規化,並將 df 收斂為恰好這些欄位。

    收斂欄位確保寫入時 df.columns 與 comments 鍵集合一致(writer 缺欄會 raise)。
    pyspark 於函式內 import,維持模組頂層無 pyspark 依賴。
    """
    from pyspark.sql import functions as F
    from pyspark.sql.types import DoubleType, IntegerType, StringType

    _INT_SUFFIXES = ("_QTY", "_ID", "_ACTIVE")
    _FLOAT_SUFFIXES = ("_AMT", "_PRICE")

    select_cols = []
    for col in columns:
        if col.endswith(_INT_SUFFIXES):
            udf = F.udf(lambda v, c=col: normalize_value(c, v), IntegerType())
        elif col.endswith(_FLOAT_SUFFIXES):
            udf = F.udf(lambda v, c=col: normalize_value(c, v), DoubleType())
        else:
            udf = F.udf(lambda v, c=col: normalize_value(c, v), StringType())
        select_cols.append(udf(F.col(col)).alias(col))
    return df.select(*select_cols)


def run(spark: Any, config: dict[str, Any]) -> None:
    """搬移 DS schema 全部(yaml 定義的)表:讀 → 轉換 → 寫入 + 套 Comment。"""
    logger = get_logger("etl.jobs.ds_migrate")
    mapping = config["mapping"]["ds"]
    tables = mapping.get("tables")
    if not isinstance(tables, dict) or not tables:
        raise ValueError("ds.yaml 缺少 tables 或為空")

    log_event(logger, "DS 搬移開始", job="ds_migrate", rows=len(tables))
    for table_name, table_def in tables.items():
        columns = _table_columns(table_def)
        comments = _table_comments(table_def)

        source_df = read_table(spark, _SOURCE_SCHEMA, table_name)
        transformed = _transform_df(source_df, columns)
        # transformed.columns == columns == comments.keys(),確保 writer comment 涵蓋全欄
        write_table(transformed, _TARGET_SCHEMA, table_name, comments)
        log_event(logger, "DS 表搬移完成", job="ds_migrate", table=table_name)

    log_event(logger, "DS 搬移完成", job="ds_migrate")
