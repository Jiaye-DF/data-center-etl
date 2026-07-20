"""seed_semantic_mappings 測試(task-002,propose A2):草稿 upsert / confirmed 不覆寫 / 轉態 / 冪等。

對齊 `test_semantic_schema.py` 模式:env 於模組匯入時導向本地測試 DB
(`localhost:5435/data_center_etl_test`),不觸碰真正 AWS RDS;
本檔覆寫為 module-level 全域,pytest 收集階段一次跑完,勿與其他測試檔互踩。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# app 模組於 import 時即讀 env 建立 engine;semantic_mappings 連線沿用 AWS_RDS_*(見 reader.py),
# 測試指向共用本地測試 DB(data_center_etl_test),不觸碰真正 AWS RDS
_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
_TEST_DB_NAME = "data_center_etl_test"

os.environ["AWS_RDS_HOST"] = _PG_HOST
os.environ["AWS_RDS_PORT"] = _PG_PORT
os.environ["AWS_RDS_USER"] = _PG_USER
os.environ["AWS_RDS_PASSWORD"] = _PG_PASSWORD
os.environ["AWS_RDS_TARGET_DB"] = _TEST_DB_NAME
os.environ.setdefault("AWS_RDS_SOURCE_DB", _TEST_DB_NAME)
os.environ.setdefault(
    "DATABASE_URL",
    f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}/{_TEST_DB_NAME}",
)
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

# scripts/ 非 package(無 __init__.py):加入 sys.path 以頂層模組名 import,
# 與 mypy 對 scripts/seed_semantic_mappings.py 的模組命名一致
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from seed_semantic_mappings import (  # noqa: E402
    run_confirm_table,
    run_seed,
)
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.etl.comments import quote_ident  # noqa: E402
from app.etl.reader import rds_database_url  # noqa: E402
from app.etl.semantic_schema import (  # noqa: E402
    SEMANTIC_SCHEMA,
    SEMANTIC_TABLE,
    ensure_semantic_schema,
)
from app.etl.writer import RDS_TARGET_DB_ENV  # noqa: E402

_QUALIFIED = f"{quote_ident(SEMANTIC_SCHEMA)}.{quote_ident(SEMANTIC_TABLE)}"

# 3 列樣本 TSV(1 表層級 + 2 欄位),對齊 Acceptance「dry-run 實測:3 列样本跑兩次恆為 3 列」
_SAMPLE_TSV = (
    "TABLE_NAME\tCOLUMN_NAME\tEN_NAME\tZH_NAME\tSRC\n"
    "AAA_FILE\t\taaa_file\t\tXXX\n"
    "AAA_FILE\tAAA01\taccount_no\t帳號\tGAE\n"
    "AAA_FILE\tAAA02\taccount_name\t帳戶名稱\tGAE\n"
)


@pytest_asyncio.fixture
async def target_engine() -> AsyncIterator[AsyncEngine]:
    """指向共用測試 DB 的 engine(NullPool,對齊 test_semantic_schema.py 模式)。"""
    engine = create_async_engine(rds_database_url(RDS_TARGET_DB_ENV), poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await ensure_semantic_schema(conn)
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_semantic_mappings(target_engine: AsyncEngine) -> AsyncIterator[None]:
    """每測試後清空表資料(非 DROP);對齊 test_semantic_schema.py 清理策略。"""
    yield
    async with target_engine.begin() as conn:
        await conn.execute(text(f"DELETE FROM {_QUALIFIED}"))


@pytest.fixture
def sample_tsv(tmp_path: Path) -> Path:
    path = tmp_path / "sample_semantic_draft.tsv"
    path.write_text(_SAMPLE_TSV, encoding="utf-8")
    return path


async def _fetch_all(target_engine: AsyncEngine) -> list[tuple[str, str, str, str | None, str]]:
    async with target_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT table_name, column_name, english_name, zh_name, status"
                    f" FROM {_QUALIFIED} ORDER BY table_name, column_name"
                )
            )
        ).all()
    return [(r.table_name, r.column_name, r.english_name, r.zh_name, r.status) for r in rows]


async def test_seed_creates_draft_rows(target_engine: AsyncEngine, sample_tsv: Path) -> None:
    """首跑:3 列樣本全數以 status='draft' insert。"""
    result = await run_seed(sample_tsv, engine=target_engine)

    assert result.inserted == 3
    assert result.updated == 0
    assert result.skipped_confirmed == 0

    rows = await _fetch_all(target_engine)
    assert len(rows) == 3
    assert all(status == "draft" for *_rest, status in rows)
    account_no = next(r for r in rows if r[1] == "AAA01")
    assert account_no[2] == "account_no"
    assert account_no[3] == "帳號"


async def test_seed_rerun_is_idempotent(target_engine: AsyncEngine, sample_tsv: Path) -> None:
    """重跑兩次:semantic_mappings 恆為 3 列(對齊 Acceptance dry-run 實測)。"""
    first = await run_seed(sample_tsv, engine=target_engine)
    second = await run_seed(sample_tsv, engine=target_engine)

    assert first.inserted == 3
    assert second.inserted == 0
    assert second.updated == 3
    assert second.skipped_confirmed == 0

    rows = await _fetch_all(target_engine)
    assert len(rows) == 3


async def test_confirmed_rows_not_overwritten(
    target_engine: AsyncEngine, sample_tsv: Path
) -> None:
    """已 confirmed 的列不被草稿值覆寫,保護人工複核成果。"""
    await run_seed(sample_tsv, engine=target_engine)
    await run_confirm_table("AAA_FILE", engine=target_engine)

    # 複核後手動修正 english_name(模擬人工複核值),重跑 seed 不得覆寫回草稿值
    async with target_engine.begin() as conn:
        await conn.execute(
            text(
                f"UPDATE {_QUALIFIED} SET english_name = :e"
                " WHERE table_name = :t AND column_name = :c"
            ),
            {"e": "account_number_confirmed", "t": "AAA_FILE", "c": "AAA01"},
        )

    result = await run_seed(sample_tsv, engine=target_engine)

    assert result.inserted == 0
    assert result.updated == 0
    assert result.skipped_confirmed == 3

    rows = await _fetch_all(target_engine)
    account_no = next(r for r in rows if r[1] == "AAA01")
    assert account_no[2] == "account_number_confirmed"
    assert account_no[4] == "confirmed"


async def test_confirm_table_transitions_status(
    target_engine: AsyncEngine, sample_tsv: Path
) -> None:
    """`--confirm-table` 轉態:指定表全部列 status 轉為 confirmed。"""
    await run_seed(sample_tsv, engine=target_engine)

    affected = await run_confirm_table("AAA_FILE", engine=target_engine)

    assert affected == 3
    rows = await _fetch_all(target_engine)
    assert all(status == "confirmed" for *_rest, status in rows)


async def test_confirm_table_only_targets_named_table(
    target_engine: AsyncEngine, sample_tsv: Path
) -> None:
    """`--confirm-table` 只轉指定表,不動其他表。"""
    await run_seed(sample_tsv, engine=target_engine)
    async with target_engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {_QUALIFIED} (table_name, column_name, english_name, status)"
                " VALUES (:t, :c, :e, 'draft')"
            ),
            {"t": "BBB_FILE", "c": "BBB01", "e": "other_col"},
        )

    affected = await run_confirm_table("AAA_FILE", engine=target_engine)

    assert affected == 3
    rows = await _fetch_all(target_engine)
    bbb_row = next(r for r in rows if r[0] == "BBB_FILE")
    assert bbb_row[4] == "draft"
