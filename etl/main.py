"""Glue Job 入口:設定驅動的動態派工。

依 config/job_config.yaml 的 job 名稱,動態 import jobs.<name>_job 並呼叫其 run(spark, config)。
新增 job 不需回頭改本檔(禁 if/elif 硬列 job 名稱)。

Glue 相容性:
- 以 parse_known_args 忽略 Glue 自動注入的內建參數(--JOB_NAME / --JOB_ID / --job-bookmark-option 等)。
- --config-s3-uri 指定 s3://bucket/prefix 的 config 來源(改 S3 上 yaml → 下次 run 生效,不需重新部署)。
- --source-db-secret-id / --target-db-secret-id 指定 Secrets Manager secret,
  啟動時解出 host/port/dbname/username/password 填入 SOURCE_DB_* / TARGET_DB_* env
  (既有 env 優先;reader / writer 維持 env 單一來源,不需改動)。

執行方式(Glue / 本地):
    python etl/main.py --job ds_migrate
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from typing import Any

try:  # Glue 上以 common.* 執行;fallback 供 repo 根以 etl.common.* 匯入
    from common.config import get_job_names, load_config
    from common.logger import get_logger, log_event
except ImportError:  # pragma: no cover
    from etl.common.config import get_job_names, load_config
    from etl.common.logger import get_logger, log_event

# Secrets Manager 標準 RDS secret JSON 鍵 → env 尾碼 對應
_SECRET_KEY_TO_ENV_SUFFIX = {
    "host": "HOST",
    "port": "PORT",
    "dbname": "NAME",
    "username": "USER",
    "password": "PASSWORD",
}


def _parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    """解析本程式關心的參數;未知參數(Glue 內建)原樣回傳、不視為錯誤。"""
    parser = argparse.ArgumentParser(description="ETL Glue Job 入口")
    parser.add_argument("--job", required=True, help="job 名稱(對應 jobs.<name>_job)")
    parser.add_argument(
        "--config-s3-uri",
        default=None,
        help="config 來源 s3://bucket/prefix;未給時依 common.config 解析順序",
    )
    parser.add_argument(
        "--source-db-secret-id",
        default=None,
        help="來源 DB 憑證的 Secrets Manager secret id(env 已有 SOURCE_DB_* 時略過)",
    )
    parser.add_argument(
        "--target-db-secret-id",
        default=None,
        help="目標 DB 憑證的 Secrets Manager secret id(env 已有 TARGET_DB_* 時略過)",
    )
    return parser.parse_known_args(argv)


def _bootstrap_db_env(env_prefix: str, secret_id: str | None) -> None:
    """由 Secrets Manager 補齊 <env_prefix>_HOST/PORT/NAME/USER/PASSWORD。

    - 既有 env 一律優先(setdefault),本地執行不受影響。
    - secret 值僅進 os.environ,禁 log(對齊 00-overview/02-secrets.md)。
    """
    if not secret_id:
        return
    needed = [f"{env_prefix}_{suffix}" for suffix in _SECRET_KEY_TO_ENV_SUFFIX.values()]
    if all(os.environ.get(k) for k in needed):
        return

    import boto3  # 延遲 import:Glue 內建;本地未裝且未用 secret 時不需要

    client = boto3.client("secretsmanager")
    secret = json.loads(client.get_secret_value(SecretId=secret_id)["SecretString"])
    for key, suffix in _SECRET_KEY_TO_ENV_SUFFIX.items():
        value = secret.get(key)
        if value is not None:
            os.environ.setdefault(f"{env_prefix}_{suffix}", str(value))


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
    args, unknown = _parse_args(argv)

    logger = get_logger("etl.main")
    if unknown:
        # 只 log 參數名不 log 值(Glue 內建參數可能含敏感路徑)
        names = [a for a in unknown if a.startswith("--")]
        log_event(logger, "忽略非本程式參數(Glue 內建)", args=",".join(names))

    _bootstrap_db_env("SOURCE_DB", args.source_db_secret_id)
    _bootstrap_db_env("TARGET_DB", args.target_db_secret_id)

    config = load_config(args.config_s3_uri)

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
