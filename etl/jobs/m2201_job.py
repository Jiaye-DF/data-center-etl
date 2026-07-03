"""M2201 對應轉換 job:DS.GAT_FILE / DS.GAQ_FILE → M2201(erp_etl_hub_test)。

供 main.py 動態派工:run(spark, config)。對照關係一律讀 config["mapping"]["m2201"],
不硬編。pyspark 於函式內 import,py_compile / import 本模組時不需 pyspark。
"""

from __future__ import annotations

from typing import Any

try:  # Glue 上以 common.* 執行;fallback 供 repo 根以 etl.common.* 匯入
    from common.logger import get_logger, log_event
    from common.reader import read_table
    from common.writer import write_table
except ImportError:  # pragma: no cover
    from etl.common.logger import get_logger, log_event
    from etl.common.reader import read_table
    from etl.common.writer import write_table

try:  # transform 純函式模組
    from transforms.m2201 import build_comments, target_columns
except ImportError:  # pragma: no cover
    from etl.transforms.m2201 import build_comments, target_columns

_SOURCE_SCHEMA = "DS"
_logger = get_logger("etl.jobs.m2201")


def _mapping(config: dict[str, Any]) -> dict[str, Any]:
    """取出 m2201 mapping;缺則 raise。"""
    mapping = config.get("mapping", {}).get("m2201")
    if not mapping:
        raise ValueError("config['mapping']['m2201'] 不存在或為空,無法執行 M2201 對應")
    return mapping


def _build_target_df(spark: Any, mapping: dict[str, Any]) -> Any:
    """依 mapping 讀來源表並組出 M2201 目標 DataFrame。

    - 每個目標欄依 source_table 從對應來源(GAT_FILE / GAQ_FILE)取 source 欄。
    - 型別轉換依 mapping 的 type 以 Spark cast 執行;對照全數來自 mapping。
    """
    from pyspark.sql import functions as F

    spark_type = {"str": "string", "int": "int", "float": "double"}

    source_dfs: dict[str, Any] = {}
    columns_by_source: dict[str, list[dict[str, Any]]] = {}
    for col in mapping.get("columns", []):
        columns_by_source.setdefault(col["source_table"], []).append(col)

    for source_table in columns_by_source:
        source_dfs[source_table] = read_table(spark, _SOURCE_SCHEMA, source_table)

    # 各來源表各自投影出其負責的目標欄(target 名 + cast),再以位置對齊合併
    projected: list[Any] = []
    for source_table, cols in columns_by_source.items():
        select_exprs = [
            F.col(col["source"]).cast(spark_type.get(col["type"], "string")).alias(col["target"])
            for col in cols
        ]
        projected.append(source_dfs[source_table].select(*select_exprs))

    result = projected[0]
    for extra in projected[1:]:
        # 佔位版無真實 join key,先以並排合併(zip);待實際 key 對齊後改 join
        result = result.crossJoin(extra) if extra.count() == 1 else result.join(extra, how="cross")

    # 依 mapping 順序重排欄位,確保 df.columns == target_columns
    return result.select(*target_columns(mapping))


def run(spark: Any, config: dict[str, Any]) -> None:
    """讀 DS.GAT_FILE / DS.GAQ_FILE,依 m2201 mapping 對映轉換,寫入 M2201。"""
    mapping = _mapping(config)
    target_schema = mapping.get("target_schema", "M2201")
    target_table = mapping.get("target_table", "M2201")

    log_event(_logger, "M2201 對應轉換開始", table=f"{target_schema}.{target_table}")

    df = _build_target_df(spark, mapping)
    comments = build_comments(mapping)

    write_table(df, target_schema, target_table, comments)

    log_event(_logger, "M2201 對應轉換完成", table=f"{target_schema}.{target_table}")
