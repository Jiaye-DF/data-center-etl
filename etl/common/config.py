"""設定載入器:讀 config/*.yaml 與 config/mapping/*.yaml,回傳合併後的 dict。

yaml 解析集中於此;其他模組禁自行 open yaml。
DB / S3 憑證等機密禁寫入 yaml,一律走 env(見 docs/Design-Base/00-overview/02-secrets.md)。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# 預設 config 根目錄:本檔位於 etl/common/config.py,往上一層即 etl/,再進 config/
_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _read_yaml(path: Path) -> dict[str, Any]:
    """讀單一 yaml 檔,空檔回傳空 dict。"""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"yaml 頂層須為 mapping:{path}")
    return data


def load_config(
    config_dir: str | os.PathLike[str] | None = None,
    *,
    job_config: str = "job_config.yaml",
    table_config: str = "table_config.yaml",
    load_mapping: bool = True,
) -> dict[str, Any]:
    """載入並合併 job / table 設定與 mapping 目錄下所有 yaml。

    回傳結構:
        {
            "jobs": {...},           # job_config.yaml 內容
            "tables": {...},         # table_config.yaml 內容
            "mapping": {stem: {...}} # config/mapping/*.yaml,以檔名(去副檔名)為 key
        }
    """
    base = Path(config_dir) if config_dir is not None else _DEFAULT_CONFIG_DIR

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
