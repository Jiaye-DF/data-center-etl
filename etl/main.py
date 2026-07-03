"""Glue Job 入口:設定驅動的動態派工。

依 config/job_config.yaml 的 job 名稱,動態 import jobs.<name>_job 並呼叫其 run(spark, config)。
新增 job 不需回頭改本檔(禁 if/elif 硬列 job 名稱)。

執行方式(Glue / 本地):
    python etl/main.py --job ds_migrate
"""

from __future__ import annotations

import argparse
import importlib
from typing import Any

try:  # Glue 上以 common.* 執行;fallback 供 repo 根以 etl.common.* 匯入
    from common.config import get_job_names, load_config
    from common.logger import get_logger, log_event
except ImportError:  # pragma: no cover
    from etl.common.config import get_job_names, load_config
    from etl.common.logger import get_logger, log_event


def _build_spark() -> Any:
    """建立 Spark session。pyspark 在函式內 import,避免缺 pyspark 時語法檢查/import 失敗。"""
    from pyspark.sql import SparkSession

    return SparkSession.builder.getOrCreate()


def dispatch(job_name: str, spark: Any, config: dict[str, Any]) -> None:
    """動態載入 jobs.<job_name>_job 並呼叫 run(spark, config)。"""
    module = importlib.import_module(f"jobs.{job_name}_job")
    run = getattr(module, "run", None)
    if not callable(run):
        raise AttributeError(f"job 模組 jobs.{job_name}_job 缺少可呼叫的 run(spark, config)")
    run(spark, config)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="ETL Glue Job 入口")
    parser.add_argument("--job", required=True, help="job 名稱(對應 jobs.<name>_job)")
    args = parser.parse_args(argv)

    logger = get_logger("etl.main")
    config = load_config()

    valid_jobs = get_job_names(config)
    if valid_jobs and args.job not in valid_jobs:
        raise SystemExit(f"未知 job:{args.job};job_config.yaml 允許:{valid_jobs}")

    log_event(logger, "job 開始", job=args.job)
    spark = _build_spark()
    try:
        dispatch(args.job, spark, config)
        log_event(logger, "job 完成", job=args.job)
    except Exception:
        log_event(logger, "job 失敗", job=args.job, level=40)
        raise


if __name__ == "__main__":
    main()
