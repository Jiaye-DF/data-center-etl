"""task-001 roles 表 + users.role_pid backfill 測試(真實 PostgreSQL,實跑 alembic migration)。

不同於既有 test_models_vNNN 系列(純 metadata 斷言),本檔需驗證「seed 存在」
「既有 user backfill 不留 NULL」「User 關聯可取角色 code」等行為性斷言,
故對獨立測試 DB 實際先跑到 v6、插一筆舊 schema 的 user,再跑到 head,
藉此驗證 v7 migration 內建表 / seed / backfill 邏輯是否正確(而非只用
create_all 建出最終 schema、略過 migration 本身的資料轉移邏輯)。
"""

import os
from pathlib import Path
from uuid import UUID, uuid4

# app.core.db 於 import 時即建立 engine → 必須先注入測試 env,再 import app 模組
_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
_PG_ADMIN_DB = os.environ.get("TEST_PG_ADMIN_DB", "data_center_etl")
# 獨立 DB 名:與其他檔共用的 data_center_etl_test(create_all-only schema)隔離,
# 避免本檔實跑 migration 的 schema 演進過程互相污染
TEST_DB_NAME = "data_center_etl_v141_test"

_BASE_URL = f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}"
ADMIN_DATABASE_URL = f"{_BASE_URL}/{_PG_ADMIN_DB}"
TEST_DATABASE_URL = f"{_BASE_URL}/{TEST_DB_NAME}"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("INIT_ADMIN_USERNAME", "test-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "test-admin-password")

import asyncio  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from alembic.command import downgrade as alembic_downgrade  # noqa: E402
from alembic.command import upgrade as alembic_upgrade  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402

_BACKEND_DIR = Path(__file__).resolve().parents[1]
# 固定值(非 uuid4 隨機):跨 pytest 重跑沿用同一筆「舊 schema user」,
# 存在性 guard 才抓得到同一列,避免 username 部分唯一索引在重跑時衝突
_LEGACY_USER_UID = UUID("00000000-0000-0000-0000-0000000000b1")


def _alembic_config() -> AlembicConfig:
    cfg = AlembicConfig(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db() -> None:
    """建立測試 DB(不存在才建)→ 跑到 head → 退版本註記到 v6 → 插一筆舊 schema
    user → 重跑到 head,藉此讓 v7 的 upgrade() 針對這筆「舊資料」真正重跑一次
    backfill(v7 downgrade 為 no-op,退版本註記不動實體 schema,安全可重跑)。

    不對既有 DB 做任何 DROP;僅本檔專用測試 DB,可重跑(idempotent)。
    """

    async def _ensure_db() -> None:
        admin_engine = create_async_engine(
            ADMIN_DATABASE_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT"
        )
        try:
            async with admin_engine.connect() as conn:
                exists = (
                    await conn.execute(
                        text("SELECT 1 FROM pg_database WHERE datname = :name"),
                        {"name": TEST_DB_NAME},
                    )
                ).scalar()
                if exists is None:
                    await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
        finally:
            await admin_engine.dispose()

    asyncio.run(_ensure_db())

    get_settings.cache_clear()
    cfg = _alembic_config()
    # 先確保跑滿到 head(涵蓋全新 DB 從零建起的情況)
    alembic_upgrade(cfg, "head")
    # 退版本註記到 v6(v7 downgrade 為 no-op,不動實體 schema);
    # 讓後續 upgrade head 時 v7.upgrade() 真正重跑一次(idempotent guard + backfill)
    alembic_downgrade(cfg, "v6")

    async def _seed_legacy_user() -> None:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                exists = (
                    await conn.execute(
                        text("SELECT 1 FROM users WHERE uid = :uid"),
                        {"uid": str(_LEGACY_USER_UID)},
                    )
                ).scalar()
                if exists is None:
                    await conn.execute(
                        text(
                            "INSERT INTO users "
                            "(uid, username, password_hash, role, created_by, updated_by) "
                            "VALUES (:uid, :username, NULL, 'admin', :uid, :uid)"
                        ),
                        {"uid": str(_LEGACY_USER_UID), "username": "v141-legacy-admin"},
                    )
        finally:
            await engine.dispose()

    asyncio.run(_seed_legacy_user())

    # 重跑到 head(套用 v7):建表/seed/加欄皆 guard 略過,backfill UPDATE 無 guard
    # 一律重跑 → 針對上面插入的舊列補上 role_pid
    alembic_upgrade(cfg, "head")


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


# ── Role model 欄位(純 metadata,不連 DB)───────────────────────────────
def test_role_table_columns() -> None:
    columns = Role.__table__.columns
    for name in ("code", "name", "description", "is_builtin"):
        assert name in columns, name
    assert columns["code"].nullable is False
    assert columns["name"].nullable is False
    assert columns["description"].nullable is True
    assert columns["is_builtin"].nullable is False


def test_role_code_partial_unique_index() -> None:
    idx = next(i for i in Role.__table__.indexes if i.name == "uq_roles_code")
    assert idx.unique
    assert idx.dialect_options["postgresql"]["where"] is not None
    assert {c.name for c in idx.columns} == {"code"}


def test_user_role_pid_fk_and_index() -> None:
    columns = User.__table__.columns
    assert "role_pid" in columns
    # task-002 前建立路徑尚未寫入 role_pid,暫不收 NOT NULL(見 fixed.md)
    assert columns["role_pid"].nullable is True
    fk_names = {fk.name for fk in User.__table__.foreign_keys}
    assert "fk_users_role" in fk_names
    idx_names = {i.name for i in User.__table__.indexes}
    assert "idx_users_role_pid" in idx_names


def test_user_role_string_column_retained_deprecated() -> None:
    """舊 role 字串欄位與 ck_users_role 約束原樣保留(deprecated,未移除)。"""
    columns = User.__table__.columns
    assert "role" in columns
    assert columns["role"].nullable is False
    check_names = {
        c.name for c in User.__table__.constraints if c.name == "ck_users_role"
    }
    assert "ck_users_role" in check_names


# ── seed 存在(migration 實跑後,真實 DB)───────────────────────────────
async def test_seed_roles_exist(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(Role).where(Role.is_deleted.is_(False)).order_by(Role.code)
            )
        ).scalars().all()
        by_code = {r.code: r for r in rows}
        assert by_code.keys() == {"admin", "viewer"}
        assert by_code["admin"].name == "管理員"
        assert by_code["admin"].is_builtin is True
        assert by_code["viewer"].name == "檢視者"
        assert by_code["viewer"].is_builtin is True


# ── backfill:migration 前既有 user 全數補上 role_pid ─────────────────────
async def test_legacy_user_backfilled_to_matching_role(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.uid == _LEGACY_USER_UID))
        ).scalar_one()
        admin_role = (
            await session.execute(select(Role).where(Role.code == "admin"))
        ).scalar_one()
        assert user.role == "admin"
        assert user.role_pid == admin_role.pid


async def test_no_null_role_pid_after_backfill(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """migration backfill 當下(head 剛套用完)既有 user 不留 NULL role_pid。"""
    async with session_factory() as session:
        rows = (
            await session.execute(select(User.username).where(User.role_pid.is_(None)))
        ).scalars().all()
        assert rows == []


# ── User 關聯可取角色 code ─────────────────────────────────────────────
async def test_user_role_ref_relationship_returns_role_code(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.uid == _LEGACY_USER_UID))
        ).scalar_one()
        assert user.role_ref is not None
        assert user.role_ref.code == "admin"


async def test_new_user_without_role_pid_still_insertable(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """role_pid 暫未收 NOT NULL:既有建立使用者路徑(尚未寫入 role_pid)不炸(fixed.md)。

    自行清理插入列(DELETE,非 DROP):本檔測試 DB 為持久複用,避免每次重跑
    在 users 表留下永久 NULL role_pid 殘列,干擾 test_no_null_role_pid_after_backfill。
    """
    new_uid = uuid4()
    async with session_factory() as session:
        session.add(
            User(
                uid=new_uid,
                username=f"v141-no-role-pid-{new_uid}",
                password_hash=None,
                role="viewer",
                created_by=new_uid,
                updated_by=new_uid,
            )
        )
        await session.commit()

    async with session_factory() as session:
        user = (await session.execute(select(User).where(User.uid == new_uid))).scalar_one()
        assert user.role_pid is None

    async with session_factory() as session:
        await session.execute(text("DELETE FROM users WHERE uid = :uid"), {"uid": str(new_uid)})
        await session.commit()
