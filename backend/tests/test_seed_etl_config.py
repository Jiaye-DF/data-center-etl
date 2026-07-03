"""task-008 seed 匯入測試:匯入筆數 / 冪等重跑 / 繁中 comment 落庫 / 缺 comment 警告。

需本地 PostgreSQL(docker compose 之 postgres,host port 5435);
測試於獨立資料庫 `data_center_etl_seed_test` 進行(自動建立,僅 DELETE 清理、禁 DROP)。
"""

import os
import sys
from pathlib import Path

# scripts/ 非 package(無 __init__.py):加入 sys.path 以頂層模組名 import,
# 與 mypy 對 scripts/seed_etl_config.py 的模組命名(seed_etl_config)一致
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

# app.core.db 於 import 時即建立 engine;僅需合法 URL 讓 Settings 可載入(不會真的連線)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
# task-002 起 Settings 必填 init_admin env;本測試不使用登入,僅供 Settings 載入
os.environ.setdefault("INIT_ADMIN_USERNAME", "test-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "test-admin-password")

from collections.abc import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402
from seed_etl_config import (  # noqa: E402
    DEFAULT_DS_YAML,
    DEFAULT_M2201_YAML,
    SYSTEM_ACTOR_UID,
    run_seed,
)
from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.db import Base  # noqa: E402
from app.models.etl_mapping import EtlMapping  # noqa: E402
from app.models.etl_table import EtlTable  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]
# 測試專用資料庫(與 dev DB data_center_etl 隔離,避免污染)
TEST_DB_NAME = "data_center_etl_seed_test"

# yaml 期望筆數(ds.yaml:GAT_FILE 5 + GAQ_FILE 5 + GAM_FILE 4;m2201.yaml:9)
EXPECTED_TABLES = 4
EXPECTED_MAPPINGS = 23


def _load_root_env() -> dict[str, str]:
    """讀專案根 .env 的 POSTGRES_* 連線資訊(禁在測試碼硬編帳密)。"""
    env_path = _REPO_ROOT / ".env"
    data: dict[str, str] = {}
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def _pg_urls() -> tuple[str, str]:
    """回傳 (admin_url, test_url):admin 連 dev DB 供 CREATE DATABASE,test 連測試 DB。"""
    root_env = _load_root_env()

    def cfg(key: str, default: str = "") -> str:
        return os.environ.get(key) or root_env.get(key) or default

    user = cfg("POSTGRES_USER")
    password = cfg("POSTGRES_PASSWORD")
    admin_db = cfg("POSTGRES_DB")
    host = cfg("POSTGRES_TEST_HOST", "localhost")
    # docker-compose.yml 將 postgres 對映至 host port 5435
    port = cfg("POSTGRES_TEST_PORT", "5435")
    if not (user and password and admin_db):
        pytest.fail("缺 PostgreSQL 連線資訊:請設定專案根 .env 或 POSTGRES_* 環境變數")
    base = f"postgresql+asyncpg://{user}:{password}@{host}:{port}"
    return f"{base}/{admin_db}", f"{base}/{TEST_DB_NAME}"


async def _ensure_test_db() -> str:
    """確保測試 DB 存在並建好資料表,清空殘留列後回傳測試 DB URL。"""
    admin_url, test_url = _pg_urls()

    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name").bindparams(
                    name=TEST_DB_NAME
                )
            )
            if exists is None:
                # 識別字為本檔模組常數(非外部輸入),CREATE DATABASE 不支援 bind param
                await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    finally:
        await admin_engine.dispose()

    engine = create_async_engine(test_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # 清理上一輪測試殘留(測試專用 DB 的 fixture 清理,非業務資料;僅 DELETE、禁 DROP)
            for table in ("etl_run_logs", "etl_runs", "schedules", "etl_mappings", "etl_tables"):
                await conn.execute(text(f"DELETE FROM {table}"))  # noqa: S608
    finally:
        await engine.dispose()
    return test_url


@pytest.fixture
async def db_url() -> str:
    return await _ensure_test_db()


@pytest.fixture
async def session(db_url: str) -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as s:
            yield s
    finally:
        await engine.dispose()


async def _count(session: AsyncSession, model: type[EtlTable] | type[EtlMapping]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def _mapping_by_target(session: AsyncSession, target_column: str) -> EtlMapping:
    row = await session.scalar(
        select(EtlMapping).where(
            EtlMapping.target_column == target_column,
            EtlMapping.is_deleted.is_(False),
        )
    )
    assert row is not None, f"找不到 target_column={target_column}"
    return row


async def test_seed_creates_expected_rows(db_url: str, session: AsyncSession) -> None:
    """首跑匯入筆數正確:4 表 / 23 對照,無缺 comment 警告。"""
    result = await run_seed(db_url, DEFAULT_DS_YAML, DEFAULT_M2201_YAML)

    assert result.tables_created == EXPECTED_TABLES
    assert result.mappings_created == EXPECTED_MAPPINGS
    assert result.tables_skipped == 0
    assert result.mappings_skipped == 0
    assert result.missing_comments == []

    assert await _count(session, EtlTable) == EXPECTED_TABLES
    assert await _count(session, EtlMapping) == EXPECTED_MAPPINGS

    # m2201 多來源表:source 以逗號合併,target 為 M2201.M2201
    m2201 = await session.scalar(
        select(EtlTable).where(EtlTable.target_table == "M2201")
    )
    assert m2201 is not None
    assert m2201.source_schema == "DS"
    assert m2201.source_table == "GAT_FILE,GAQ_FILE"
    assert m2201.target_schema == "M2201"
    assert m2201.is_enabled is True
    assert m2201.created_by == SYSTEM_ACTOR_UID

    # m2201 mapping 的 source_column 保留「來源表.欄名」出處
    doc_no = await _mapping_by_target(session, "DOC_NO")
    assert doc_no.source_column == "GAT_FILE.GAT_NO"
    assert doc_no.transform_type == "str"

    # DS 表 1:1 搬移 + 欄名尾碼推斷型別(同 etl/transforms/ds.py 行為)
    gat_qty = await _mapping_by_target(session, "GAT_QTY")
    assert gat_qty.source_column == "GAT_QTY"
    assert gat_qty.transform_type == "int"
    gat_amt = await _mapping_by_target(session, "GAT_AMT")
    assert gat_amt.transform_type == "float"
    gam_active = await _mapping_by_target(session, "GAM_ACTIVE")
    assert gam_active.transform_type == "int"
    gat_memo = await _mapping_by_target(session, "GAT_MEMO")
    assert gat_memo.transform_type == "str"


async def test_seed_rerun_is_idempotent(db_url: str, session: AsyncSession) -> None:
    """冪等:重跑不重複建,筆數不變、既有資料不覆寫。"""
    await run_seed(db_url, DEFAULT_DS_YAML, DEFAULT_M2201_YAML)
    second = await run_seed(db_url, DEFAULT_DS_YAML, DEFAULT_M2201_YAML)

    assert second.tables_created == 0
    assert second.mappings_created == 0
    assert second.tables_skipped == EXPECTED_TABLES
    assert second.mappings_skipped == EXPECTED_MAPPINGS
    assert second.tables_updated == 0
    assert second.mappings_updated == 0

    assert await _count(session, EtlTable) == EXPECTED_TABLES
    assert await _count(session, EtlMapping) == EXPECTED_MAPPINGS


async def test_zh_tw_comments_persisted(db_url: str, session: AsyncSession) -> None:
    """繁中 comment 正確落庫(utf-8 讀 yaml,不受 Windows cp950 影響)。"""
    await run_seed(db_url, DEFAULT_DS_YAML, DEFAULT_M2201_YAML)

    doc_no = await _mapping_by_target(session, "DOC_NO")
    assert doc_no.comment == "單據編號(主鍵,字串)"
    gaq_no = await _mapping_by_target(session, "GAQ_NO")
    assert gaq_no.comment == "報價單號(主鍵,字串)"
    unit_price = await _mapping_by_target(session, "UNIT_PRICE")
    assert unit_price.comment == "單價(浮點)"


async def test_rerun_keeps_manual_edits_unless_force_update(
    db_url: str, session: AsyncSession
) -> None:
    """既有資料不覆寫;帶 force_update 才以 yaml 覆寫回來。"""
    await run_seed(db_url, DEFAULT_DS_YAML, DEFAULT_M2201_YAML)

    doc_no = await _mapping_by_target(session, "DOC_NO")
    doc_no.comment = "後台人工修改後的說明"
    await session.commit()

    # 不帶 force_update:人工修改保留
    await run_seed(db_url, DEFAULT_DS_YAML, DEFAULT_M2201_YAML)
    session.expire_all()
    doc_no = await _mapping_by_target(session, "DOC_NO")
    assert doc_no.comment == "後台人工修改後的說明"

    # 帶 force_update:覆寫回 yaml 值
    forced = await run_seed(db_url, DEFAULT_DS_YAML, DEFAULT_M2201_YAML, force_update=True)
    assert forced.mappings_updated == EXPECTED_MAPPINGS
    assert forced.tables_updated == EXPECTED_TABLES
    session.expire_all()
    doc_no = await _mapping_by_target(session, "DOC_NO")
    assert doc_no.comment == "單據編號(主鍵,字串)"


async def test_missing_comment_warns_but_continues(
    db_url: str, session: AsyncSession, tmp_path: Path
) -> None:
    """缺 comment 欄位列入警告清單但不中斷,以空字串落庫供後台補齊。"""
    ds_yaml = tmp_path / "ds.yaml"
    ds_yaml.write_text(
        "tables:\n"
        "  X_FILE:\n"
        "    columns:\n"
        "      X_NO:\n"
        '        comment: "測試編號"\n'
        "      X_QTY: {}\n",
        encoding="utf-8",
    )
    m2201_yaml = tmp_path / "m2201.yaml"
    m2201_yaml.write_text(
        "target_table: M9999\n"
        "target_schema: M9999\n"
        "columns:\n"
        "  - target: Y_NO\n"
        "    source: Z_NO\n"
        "    source_table: Z_FILE\n"
        "    type: str\n"
        '    comment: ""\n',
        encoding="utf-8",
    )

    result = await run_seed(db_url, ds_yaml, m2201_yaml)

    assert result.tables_created == 2
    assert result.mappings_created == 3
    assert set(result.missing_comments) == {"DS.X_FILE.X_QTY", "M9999.M9999.Y_NO"}

    x_qty = await _mapping_by_target(session, "X_QTY")
    assert x_qty.comment == ""
    x_no = await _mapping_by_target(session, "X_NO")
    assert x_no.comment == "測試編號"
