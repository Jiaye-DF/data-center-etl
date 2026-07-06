"""v1.0.0 mapping 設定匯入自有 DB(seed)。

讀取 v1.0.0 `etl/config/mapping/ds.yaml` / `m2201.yaml`(唯讀來源,不改 `etl/` 任何檔),
匯入 `etl_tables` / `etl_mappings` 作為後台初始資料。

- 冪等:重跑不重複建;既有資料不覆寫,除非帶 `--force-update`
- yaml 一律以 encoding="utf-8" 開啟(繁中 comment;見 docs/Tasks/v1.0.0/fixed.md § 1–2)
- 匯入時驗證每欄位有 comment:缺值列警告清單(不中斷,空字串落庫,後台可補)

用法(於 backend/ 目錄;需可載入 app Settings 的 env,如 DATABASE_URL / INIT_ADMIN_*):
    uv run python scripts/seed_etl_config.py [--ds-yaml PATH] [--m2201-yaml PATH]
        [--database-url URL] [--force-update]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import yaml

# 以 `python scripts/seed_etl_config.py` 直跑時,需把 backend/ 加入 sys.path 才能 import app.*
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models.etl_mapping import EtlMapping  # noqa: E402
from app.models.etl_table import EtlTable  # noqa: E402

# seed 為系統動作,無登入使用者 → 以全零 UUID 代表系統帳號(created_by / updated_by)
SYSTEM_ACTOR_UID = UUID("00000000-0000-0000-0000-000000000000")

# 預設 yaml 路徑:<repo root>/etl/config/mapping/*.yaml(v1.0.0 來源,唯讀)
_REPO_ROOT = _BACKEND_DIR.parent
DEFAULT_DS_YAML = _REPO_ROOT / "etl" / "config" / "mapping" / "ds.yaml"
DEFAULT_M2201_YAML = _REPO_ROOT / "etl" / "config" / "mapping" / "m2201.yaml"

# DS 欄名尾碼 → 型別轉換規則(行為移植自 etl/transforms/ds.py,唯讀參考不修改)
_INT_SUFFIXES = ("_QTY", "_ID", "_ACTIVE")
_FLOAT_SUFFIXES = ("_AMT", "_PRICE")

DS_SCHEMA = "DS"


@dataclass
class MappingSeed:
    """單一欄位對照的 seed 資料。"""

    source_column: str
    target_column: str
    transform_type: str | None
    comment: str
    sort_order: int


@dataclass
class TableSeed:
    """單一 ETL 表(含其欄位對照)的 seed 資料。"""

    source_schema: str
    source_table: str
    target_schema: str
    target_table: str
    description: str | None
    mappings: list[MappingSeed] = field(default_factory=list)


@dataclass
class SeedResult:
    """seed 執行結果統計(供 CLI 輸出與測試斷言)。"""

    tables_created: int = 0
    tables_skipped: int = 0
    tables_updated: int = 0
    mappings_created: int = 0
    mappings_skipped: int = 0
    mappings_updated: int = 0
    # 缺 comment 的欄位識別清單(如 "DS.GAT_FILE.GAT_NO"),僅警告不中斷
    missing_comments: list[str] = field(default_factory=list)


def infer_ds_transform(column: str) -> str:
    """依 DS 欄名尾碼推斷型別轉換規則(同 etl/transforms/ds.py 行為)。"""
    if column.endswith(_INT_SUFFIXES):
        return "int"
    if column.endswith(_FLOAT_SUFFIXES):
        return "float"
    return "str"


def load_yaml(path: Path) -> dict[str, object]:
    """以 UTF-8 讀取 yaml(繁中 comment;禁裸 open,見 v1.0.0 fixed.md § 1–2)。"""
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"yaml 內容非 dict:{path}")
    return data


def build_seed_entries(
    ds_cfg: dict[str, object], m2201_cfg: dict[str, object], result: SeedResult
) -> list[TableSeed]:
    """由 ds / m2201 yaml 內容組出 seed 條目;缺 comment 記入 result.missing_comments。"""
    entries: list[TableSeed] = []

    # --- ds.yaml:DS schema 表 1:1 搬移(source = target,轉換規則由欄名尾碼推斷)---
    ds_tables: dict[str, object] = ds_cfg.get("tables") or {}
    for table_name, spec in ds_tables.items():
        columns: dict[str, object] = (spec or {}).get("columns") or {}
        entry = TableSeed(
            source_schema=DS_SCHEMA,
            source_table=str(table_name),
            target_schema=DS_SCHEMA,
            target_table=str(table_name),
            description=f"v1.0.0 ds.yaml 匯入:DS.{table_name} 1:1 搬移",
        )
        for sort_order, (col_name, col_spec) in enumerate(columns.items()):
            comment = str((col_spec or {}).get("comment") or "").strip()
            if not comment:
                result.missing_comments.append(f"DS.{table_name}.{col_name}")
            entry.mappings.append(
                MappingSeed(
                    source_column=str(col_name),
                    target_column=str(col_name),
                    transform_type=infer_ds_transform(str(col_name)),
                    comment=comment,
                    sort_order=sort_order,
                )
            )
        entries.append(entry)

    # --- m2201.yaml:多來源(GAT_FILE/GAQ_FILE)→ 單一目標表 ---
    target_schema = str(m2201_cfg.get("target_schema") or "")
    target_table = str(m2201_cfg.get("target_table") or "")
    columns_list: list[dict[str, object]] = m2201_cfg.get("columns") or []
    # 來源表依 yaml 出現順序去重,合併為逗號分隔字串(etl_tables 單來源欄位的多來源表示法)
    source_tables: list[str] = []
    for col in columns_list:
        st = str(col.get("source_table") or "")
        if st and st not in source_tables:
            source_tables.append(st)
    m2201_entry = TableSeed(
        source_schema=DS_SCHEMA,
        source_table=",".join(source_tables),
        target_schema=target_schema,
        target_table=target_table,
        description=(
            f"v1.0.0 m2201.yaml 匯入:{' + '.join(source_tables)} → "
            f"{target_schema}.{target_table}(多來源以逗號分隔)"
        ),
    )
    for sort_order, col in enumerate(columns_list):
        comment = str(col.get("comment") or "").strip()
        target_col = str(col.get("target") or "")
        if not comment:
            result.missing_comments.append(f"{target_schema}.{target_table}.{target_col}")
        raw_type = col.get("type")
        m2201_entry.mappings.append(
            MappingSeed(
                # 多來源表 → source_column 以「來源表.欄名」保留欄位出處
                source_column=f"{col.get('source_table')}.{col.get('source')}",
                target_column=target_col,
                transform_type=str(raw_type) if raw_type else None,
                comment=comment,
                sort_order=sort_order,
            )
        )
    entries.append(m2201_entry)
    return entries


async def _seed_mappings(
    session: AsyncSession,
    table_pid: int,
    mappings: list[MappingSeed],
    force_update: bool,
    result: SeedResult,
) -> None:
    """對單一 etl_table 寫入欄位對照:缺的補建、既有預設不覆寫(--force-update 才更新)。"""
    existing_rows = (
        await session.scalars(
            select(EtlMapping).where(
                EtlMapping.etl_table_pid == table_pid,
                EtlMapping.is_deleted.is_(False),
            )
        )
    ).all()
    existing_by_target = {row.target_column: row for row in existing_rows}

    for m in mappings:
        row = existing_by_target.get(m.target_column)
        if row is None:
            session.add(
                EtlMapping(
                    etl_table_pid=table_pid,
                    source_column=m.source_column,
                    target_column=m.target_column,
                    transform_type=m.transform_type,
                    comment=m.comment,
                    sort_order=m.sort_order,
                    created_by=SYSTEM_ACTOR_UID,
                    updated_by=SYSTEM_ACTOR_UID,
                )
            )
            result.mappings_created += 1
        elif force_update:
            row.source_column = m.source_column
            row.transform_type = m.transform_type
            row.comment = m.comment
            row.sort_order = m.sort_order
            row.updated_by = SYSTEM_ACTOR_UID
            result.mappings_updated += 1
        else:
            result.mappings_skipped += 1


async def seed(
    session: AsyncSession, entries: list[TableSeed], *, force_update: bool = False
) -> SeedResult:
    """把 seed 條目冪等寫入 etl_tables / etl_mappings(既有資料不覆寫,除非 force_update)。"""
    result = SeedResult()
    for entry in entries:
        table = await session.scalar(
            select(EtlTable).where(
                EtlTable.source_schema == entry.source_schema,
                EtlTable.source_table == entry.source_table,
                EtlTable.is_deleted.is_(False),
            )
        )
        if table is None:
            table = EtlTable(
                source_schema=entry.source_schema,
                source_table=entry.source_table,
                target_schema=entry.target_schema,
                target_table=entry.target_table,
                description=entry.description,
                created_by=SYSTEM_ACTOR_UID,
                updated_by=SYSTEM_ACTOR_UID,
            )
            session.add(table)
            await session.flush()  # 取得 pid 供 mapping FK
            result.tables_created += 1
        elif force_update:
            table.target_schema = entry.target_schema
            table.target_table = entry.target_table
            table.description = entry.description
            table.updated_by = SYSTEM_ACTOR_UID
            result.tables_updated += 1
        else:
            result.tables_skipped += 1

        await _seed_mappings(session, table.pid, entry.mappings, force_update, result)

    await session.commit()
    return result


async def run_seed(
    database_url: str,
    ds_yaml: Path,
    m2201_yaml: Path,
    *,
    force_update: bool = False,
) -> SeedResult:
    """載入 yaml → 建 engine/session → 執行 seed(CLI 與測試共用入口)。"""
    pre_result = SeedResult()
    entries = build_seed_entries(load_yaml(ds_yaml), load_yaml(m2201_yaml), pre_result)
    engine = create_async_engine(database_url)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            result = await seed(session, entries, force_update=force_update)
        result.missing_comments = pre_result.missing_comments
        return result
    finally:
        await engine.dispose()


def _default_database_url() -> str:
    """CLI 未帶 --database-url 時,取 app Settings 的 DATABASE_URL(env 注入)。"""
    from app.core.config import get_settings

    return get_settings().DATABASE_URL


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v1.0.0 mapping 設定匯入自有 DB(seed)")
    parser.add_argument("--ds-yaml", type=Path, default=DEFAULT_DS_YAML, help="ds.yaml 路徑")
    parser.add_argument(
        "--m2201-yaml", type=Path, default=DEFAULT_M2201_YAML, help="m2201.yaml 路徑"
    )
    parser.add_argument(
        "--database-url", default=None, help="自有 DB 連線 URL(預設取 env DATABASE_URL)"
    )
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="覆寫既有資料(預設冪等跳過,不覆寫)",
    )
    args = parser.parse_args(argv)

    database_url: str = args.database_url or _default_database_url()
    result = asyncio.run(
        run_seed(
            database_url,
            args.ds_yaml,
            args.m2201_yaml,
            force_update=args.force_update,
        )
    )

    print(
        "seed 完成:"
        f"tables 新建 {result.tables_created} / 跳過 {result.tables_skipped} / "
        f"更新 {result.tables_updated};"
        f"mappings 新建 {result.mappings_created} / 跳過 {result.mappings_skipped} / "
        f"更新 {result.mappings_updated}"
    )
    if result.missing_comments:
        print("警告:下列欄位缺 comment(已以空字串落庫,請於後台補齊):")
        for item in result.missing_comments:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
