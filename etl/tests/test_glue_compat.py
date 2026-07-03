"""Glue 相容層單元測試:參數解析 / config 來源解析 / partition 選項 / secret bootstrap。

不需真連 AWS / DB;S3 與 Secrets Manager 路徑僅測「不觸發」的分支
(真實讀取屬部署環境人工驗收,見 etl/README.md)。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# 確保 etl/ 在 sys.path(不論從 etl/ 或 repo 根執行皆可 import)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import (  # noqa: E402
    _resolve_config_source,
    _split_s3_uri,
    load_config,
)
from common.reader import partition_options  # noqa: E402
from main import _bootstrap_db_env, _parse_args  # noqa: E402


# ─── main._parse_args:Glue 內建參數容忍 ───────────────────────────────


def test_parse_args_ignores_glue_builtin_args() -> None:
    args, unknown = _parse_args(
        [
            "--job",
            "ds_migrate",
            "--JOB_NAME",
            "my-glue-job",
            "--JOB_ID",
            "jr_abc",
            "--job-bookmark-option",
            "job-bookmark-disable",
        ]
    )
    assert args.job == "ds_migrate"
    assert "--JOB_NAME" in unknown


def test_parse_args_custom_glue_arguments() -> None:
    args, _ = _parse_args(
        [
            "--job",
            "m2201",
            "--config-s3-uri",
            "s3://bucket/etl/config/",
            "--source-db-secret-id",
            "src-secret",
            "--target-db-secret-id",
            "tgt-secret",
        ]
    )
    assert args.config_s3_uri == "s3://bucket/etl/config/"
    assert args.source_db_secret_id == "src-secret"
    assert args.target_db_secret_id == "tgt-secret"


# ─── config 來源解析 ─────────────────────────────────────────────────


def test_split_s3_uri() -> None:
    assert _split_s3_uri("s3://bkt/etl/config/") == ("bkt", "etl/config/")
    assert _split_s3_uri("s3://bkt/etl/config") == ("bkt", "etl/config/")
    assert _split_s3_uri("s3://bkt") == ("bkt", "")
    with pytest.raises(ValueError):
        _split_s3_uri("s3:///no-bucket")


def test_resolve_explicit_s3_uri_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ETL_CONFIG_S3_URI", "s3://env-bucket/x/")
    assert _resolve_config_source("s3://arg-bucket/y/") == "s3://arg-bucket/y/"


def test_resolve_env_s3_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ETL_CONFIG_S3_URI", "s3://env-bucket/etl/config/")
    monkeypatch.delenv("ETL_CONFIG_DIR", raising=False)
    assert _resolve_config_source(None) == "s3://env-bucket/etl/config/"


def test_resolve_env_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ETL_CONFIG_S3_URI", raising=False)
    monkeypatch.setenv("ETL_CONFIG_DIR", str(tmp_path))
    assert _resolve_config_source(None) == tmp_path


def test_load_config_from_env_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "job_config.yaml").write_text("jobs:\n  - name: demo\n", encoding="utf-8")
    (tmp_path / "table_config.yaml").write_text("source:\n  database: d\n", encoding="utf-8")
    (tmp_path / "mapping").mkdir()
    (tmp_path / "mapping" / "demo.yaml").write_text("tables: {}\n", encoding="utf-8")

    monkeypatch.delenv("ETL_CONFIG_S3_URI", raising=False)
    monkeypatch.setenv("ETL_CONFIG_DIR", str(tmp_path))
    config = load_config()
    assert config["jobs"]["jobs"][0]["name"] == "demo"
    assert "demo" in config["mapping"]


# ─── reader.partition_options ────────────────────────────────────────


def test_partition_options_none_is_empty() -> None:
    assert partition_options(None) == {}


def test_partition_options_full() -> None:
    opts = partition_options(
        {"column": "pid", "num_partitions": 8, "lower_bound": 1, "upper_bound": 500000}
    )
    assert opts == {
        "partitionColumn": "pid",
        "numPartitions": "8",
        "lowerBound": "1",
        "upperBound": "500000",
    }


def test_partition_options_missing_key_raises() -> None:
    with pytest.raises(ValueError):
        partition_options({"column": "pid", "num_partitions": 8})


def test_partition_options_illegal_column_raises() -> None:
    with pytest.raises(ValueError):
        partition_options(
            {"column": "pid; DROP", "num_partitions": 4, "lower_bound": 0, "upper_bound": 1}
        )


# ─── main._bootstrap_db_env ──────────────────────────────────────────


def test_bootstrap_noop_without_secret_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOURCE_DB_HOST", raising=False)
    _bootstrap_db_env("SOURCE_DB", None)  # 不應觸發 boto3 import / 例外
    assert os.environ.get("SOURCE_DB_HOST") is None


def test_bootstrap_skips_when_env_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    for suffix, value in (
        ("HOST", "h"),
        ("PORT", "5432"),
        ("NAME", "db"),
        ("USER", "u"),
        ("PASSWORD", "p"),
    ):
        monkeypatch.setenv(f"TARGET_DB_{suffix}", value)
    # env 已齊全 → 提前 return,不呼叫 Secrets Manager(否則本測試環境會因無憑證失敗)
    _bootstrap_db_env("TARGET_DB", "some-secret-id")
    assert os.environ["TARGET_DB_HOST"] == "h"
