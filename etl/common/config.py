"""設定載入器:讀 config/*.yaml 與 config/mapping/*.yaml,回傳合併後的 dict。

yaml 解析集中於此;其他模組禁自行 open yaml。
DB / S3 憑證等機密禁寫入 yaml,一律走 env(見 docs/Design-Base/00-overview/02-secrets.md)。

設定來源解析順序(load_config 未顯式給 config_dir 時):
    1. env ETL_CONFIG_S3_URI(s3://bucket/prefix,Glue 上由 main.py 以 --config-s3-uri 注入)
    2. env ETL_CONFIG_DIR(本地目錄)
    3. <cwd>/config(存在才用;涵蓋 Glue --extra-files 落到工作目錄的情境)
    4. 本檔相對的 etl/config/(repo 內本地執行)

config_dir 亦接受 s3:// URI 字串 — 改 S3 上的 yaml 即改變下次 run 的行為,不需重新部署程式碼。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# 預設 config 根目錄:本檔位於 etl/common/config.py,往上一層即 etl/,再進 config/
_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _read_yaml_text(text: str, source: str) -> dict[str, Any]:
    """解析 yaml 字串,空內容回傳空 dict;頂層非 mapping raise。"""
    data = yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"yaml 頂層須為 mapping:{source}")
    return data


def _read_yaml(path: Path) -> dict[str, Any]:
    """讀單一 yaml 檔,空檔回傳空 dict。"""
    with path.open("r", encoding="utf-8") as f:
        return _read_yaml_text(f.read(), str(path))


def _is_s3_uri(value: str | os.PathLike[str] | None) -> bool:
    return isinstance(value, str) and value.startswith("s3://")


def _split_s3_uri(uri: str) -> tuple[str, str]:
    """s3://bucket/prefix → (bucket, prefix);prefix 正規化為結尾單一 '/' 或空字串。"""
    rest = uri[len("s3://") :]
    bucket, _, prefix = rest.partition("/")
    if not bucket:
        raise ValueError(f"非法 S3 URI(缺 bucket):{uri!r}")
    prefix = prefix.strip("/")
    return bucket, f"{prefix}/" if prefix else ""


def _load_from_s3(
    uri: str,
    *,
    job_config: str,
    table_config: str,
    load_mapping: bool,
) -> dict[str, Any]:
    """從 s3://bucket/prefix 讀 job / table / mapping yaml(Glue 執行環境內建 boto3)。"""
    import boto3  # 延遲 import:本地無 boto3 時仍可走檔案系統路徑

    bucket, prefix = _split_s3_uri(uri)
    s3 = boto3.client("s3")

    def _get(key: str) -> dict[str, Any]:
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
        return _read_yaml_text(body, f"s3://{bucket}/{key}")

    result: dict[str, Any] = {
        "jobs": _get(f"{prefix}{job_config}"),
        "tables": _get(f"{prefix}{table_config}"),
        "mapping": {},
    }

    if load_mapping:
        mapping_prefix = f"{prefix}mapping/"
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=mapping_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not key.endswith(".yaml"):
                    continue
                stem = key.rsplit("/", 1)[-1][: -len(".yaml")]
                result["mapping"][stem] = _get(key)

    return result


def _resolve_config_source(
    config_dir: str | os.PathLike[str] | None,
) -> str | Path:
    """依模組 docstring 的解析順序決定設定來源(s3:// 字串或本地 Path)。"""
    if config_dir is not None:
        return config_dir if _is_s3_uri(config_dir) else Path(config_dir)
    env_s3 = os.environ.get("ETL_CONFIG_S3_URI")
    if env_s3:
        return env_s3
    env_dir = os.environ.get("ETL_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    cwd_config = Path.cwd() / "config"
    if cwd_config.is_dir():
        return cwd_config
    return _DEFAULT_CONFIG_DIR


def load_config(
    config_dir: str | os.PathLike[str] | None = None,
    *,
    job_config: str = "job_config.yaml",
    table_config: str = "table_config.yaml",
    load_mapping: bool = True,
) -> dict[str, Any]:
    """載入並合併 job / table 設定與 mapping 目錄下所有 yaml。

    config_dir 可為本地目錄或 s3://bucket/prefix;未給時依模組 docstring 順序解析。

    回傳結構:
        {
            "jobs": {...},           # job_config.yaml 內容
            "tables": {...},         # table_config.yaml 內容
            "mapping": {stem: {...}} # config/mapping/*.yaml,以檔名(去副檔名)為 key
        }
    """
    source = _resolve_config_source(config_dir)

    if _is_s3_uri(source):
        return _load_from_s3(
            str(source),
            job_config=job_config,
            table_config=table_config,
            load_mapping=load_mapping,
        )

    base = Path(source)
    result: dict[str, Any] = {
        "jobs": _read_yaml(base / job_config),
        "tables": _read_yaml(base / table_config),
        "mapping": {},
    }

    if load_mapping:
        mapping_dir = base / "mapping"
        if mapping_dir.is_dir():
            for path in sorted(mapping_dir.glob("*.yaml")):
                result["mapping"][path.stem] = _read_yaml(path)

    return result


def get_job_names(config: dict[str, Any]) -> list[str]:
    """從已載入設定取出 job 名稱清單。

    支援兩種 job_config 結構:
        jobs: [ds_migrate, m2201]                 # 直接清單
        jobs: [{name: ds_migrate}, {name: m2201}] # 物件清單
    """
    jobs = config.get("jobs", {}).get("jobs", [])
    names: list[str] = []
    for item in jobs:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and "name" in item:
            names.append(str(item["name"]))
    return names
