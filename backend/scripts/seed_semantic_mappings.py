"""英文草稿匯入 RDS `erp_metadata.semantic_mappings` + 複核轉態(task-002,propose A2)。

讀取全量英文草稿 TSV(預設 `docs/ERP-Analyze/data/semantic_draft.tsv`;333 表 + 11,947 欄),
逐列 upsert 進目標 RDS `erp_metadata.semantic_mappings`:
- 不存在 → insert `status='draft'`
- 已存在且 `status='confirmed'` → **不覆寫**(保護人工複核成果)
- 已存在且 `status='draft'` → 更新 `english_name` / `zh_name`

複核本身延後(user 決議),本腳本只建機制;附 `--confirm-table` 供將指定表全部列
`status` 轉為 `confirmed`(複核用 / 驗收樣本表用)。

連線沿用 `app.etl.reader.rds_database_url`(目標 RDS,`AWS_RDS_TARGET_DB`),
建表沿用 task-001 `ensure_semantic_schema`(冪等,不刪除既有結構)。

用法(於 backend/ 目錄;需 `AWS_RDS_HOST/PORT/USER/PASSWORD/AWS_RDS_TARGET_DB` env):
    uv run python scripts/seed_semantic_mappings.py [--tsv PATH]
    uv run python scripts/seed_semantic_mappings.py --confirm-table BMA_FILE
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

# 以 `python scripts/seed_semantic_mappings.py` 直跑時,需把 backend/ 加入 sys.path 才能 import app.*
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine  # noqa: E402

from app.etl.comments import quote_ident  # noqa: E402
from app.etl.reader import rds_database_url  # noqa: E402
from app.etl.semantic_schema import (  # noqa: E402
    SEMANTIC_SCHEMA,
    SEMANTIC_TABLE,
    ensure_semantic_schema,
)
from app.etl.writer import RDS_TARGET_DB_ENV  # noqa: E402

_QUALIFIED = f"{quote_ident(SEMANTIC_SCHEMA)}.{quote_ident(SEMANTIC_TABLE)}"

# 預設 TSV 路徑:<repo root>/docs/ERP-Analyze/data/semantic_draft.tsv(全量英文草稿,唯讀來源)
_REPO_ROOT = _BACKEND_DIR.parent
DEFAULT_TSV = _REPO_ROOT / "docs" / "ERP-Analyze" / "data" / "semantic_draft.tsv"

_SELECT_EXISTING_SQL = text(
    f"SELECT table_name, column_name, status FROM {_QUALIFIED}"
)
_INSERT_SQL = text(
    f"INSERT INTO {_QUALIFIED} (table_name, column_name, english_name, zh_name, status)"
    " VALUES (:t, :c, :e, :z, 'draft')"
)
# updated_at 為 naive timestamp(datetime2 等價);RDS 系統時鐘為 UTC,需轉出 UTC+8 本地值
_UPDATE_DRAFT_SQL = text(
    f"UPDATE {_QUALIFIED} SET english_name = :e, zh_name = :z,"
    " updated_at = (now() AT TIME ZONE 'Asia/Taipei')"
    " WHERE table_name = :t AND column_name = :c"
)
_CONFIRM_TABLE_SQL = text(
    f"UPDATE {_QUALIFIED} SET status = 'confirmed',"
    " updated_at = (now() AT TIME ZONE 'Asia/Taipei') WHERE table_name = :t"
)


@dataclass(frozen=True)
class DraftRow:
    """單列英文草稿(TSV 一列)。"""

    table_name: str
    column_name: str
    english_name: str
    zh_name: str


@dataclass
class SeedResult:
    """seed 執行結果統計(供 CLI 輸出與測試斷言)。"""

    inserted: int = 0
    updated: int = 0
    skipped_confirmed: int = 0


def load_tsv(path: Path) -> list[DraftRow]:
    """以 UTF-8 讀取草稿 TSV(欄位 TABLE_NAME/COLUMN_NAME/EN_NAME/ZH_NAME/SRC)。

    `column_name` 空字串代表表層級映射(與目標表 PK 語意一致);`SRC` 僅供人工追溯,不落庫。
    """
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return [
            DraftRow(
                table_name=str(row["TABLE_NAME"] or "").strip(),
                column_name=str(row["COLUMN_NAME"] or "").strip(),
                english_name=str(row["EN_NAME"] or "").strip(),
                zh_name=str(row["ZH_NAME"] or "").strip(),
            )
            for row in reader
        ]


async def seed(engine: AsyncEngine, rows: list[DraftRow]) -> SeedResult:
    """把草稿列冪等寫入 semantic_mappings:既有 confirmed 不覆寫,draft 以草稿值更新。

    先一次讀出既有列狀態(對齊 `seed_etl_config.py` 的 existing-lookup 風格),
    以複合鍵 `(table_name, column_name)` 分流新增 / 更新 / 略過,值一律 bind params。
    """
    result = SeedResult()
    async with engine.begin() as conn:
        existing_rows = (await conn.execute(_SELECT_EXISTING_SQL)).all()
        existing_status = {(r.table_name, r.column_name): r.status for r in existing_rows}

        insert_params: list[dict[str, object]] = []
        update_params: list[dict[str, object]] = []
        for row in rows:
            status = existing_status.get((row.table_name, row.column_name))
            params: dict[str, object] = {
                "t": row.table_name,
                "c": row.column_name,
                "e": row.english_name,
                "z": row.zh_name,
            }
            if status is None:
                insert_params.append(params)
            elif status == "confirmed":
                result.skipped_confirmed += 1
            else:
                update_params.append(params)

        if insert_params:
            await conn.execute(_INSERT_SQL, insert_params)
        if update_params:
            await conn.execute(_UPDATE_DRAFT_SQL, update_params)

        result.inserted = len(insert_params)
        result.updated = len(update_params)
    return result


async def confirm_table(engine: AsyncEngine, table_name: str) -> int:
    """把指定表全部列 `status` 轉為 `confirmed`(複核用 / 驗收樣本表用);回傳受影響列數。"""
    async with engine.begin() as conn:
        cursor_result = await conn.execute(_CONFIRM_TABLE_SQL, {"t": table_name})
    return int(cursor_result.rowcount)


async def run_seed(tsv_path: Path, *, engine: AsyncEngine | None = None) -> SeedResult:
    """讀 TSV → 確保 schema/表存在(不刪除既有結構)→ 執行 seed(CLI 與測試共用入口)。"""
    rows = load_tsv(tsv_path)
    owns_engine = engine is None
    eng = engine or create_async_engine(rds_database_url(RDS_TARGET_DB_ENV))
    try:
        async with eng.begin() as conn:
            await ensure_semantic_schema(conn)
        return await seed(eng, rows)
    finally:
        if owns_engine:
            await eng.dispose()


async def run_confirm_table(table_name: str, *, engine: AsyncEngine | None = None) -> int:
    """CLI `--confirm-table` 入口:確保 schema/表存在 → 轉態(CLI 與測試共用入口)。"""
    owns_engine = engine is None
    eng = engine or create_async_engine(rds_database_url(RDS_TARGET_DB_ENV))
    try:
        async with eng.begin() as conn:
            await ensure_semantic_schema(conn)
        return await confirm_table(eng, table_name)
    finally:
        if owns_engine:
            await eng.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="英文草稿匯入 RDS erp_metadata.semantic_mappings(status='draft')"
    )
    parser.add_argument("--tsv", type=Path, default=DEFAULT_TSV, help="英文草稿 TSV 路徑")
    parser.add_argument(
        "--confirm-table",
        default=None,
        metavar="TABLE_NAME",
        help="將指定表全部列 status 轉為 confirmed(複核用 / 驗收樣本表用)",
    )
    args = parser.parse_args(argv)

    if args.confirm_table:
        affected = asyncio.run(run_confirm_table(args.confirm_table))
        print(f"複核轉態完成:{args.confirm_table} 共 {affected} 列轉為 confirmed")
        return 0

    result = asyncio.run(run_seed(args.tsv))
    print(
        "seed 完成:"
        f"新增 {result.inserted} / 更新 {result.updated} / "
        f"略過(已複核) {result.skipped_confirmed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
