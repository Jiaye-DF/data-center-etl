"""v1.1.0 models 欄位 / 約束斷言(純 metadata 檢查,不連 DB)。"""

import os

# app.core.db 於 import 時即建立 engine,測試不連 DB,僅需合法 URL 讓 Settings 可載入
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test"
)

from typing import cast  # noqa: E402

from sqlalchemy import CheckConstraint, Index, Table  # noqa: E402

from app.models import (  # noqa: E402
    BaseModel,
    EtlMapping,
    EtlRun,
    EtlRunLog,
    EtlTable,
    Schedule,
    User,
)

ALL_MODELS = [User, EtlTable, EtlMapping, Schedule, EtlRun, EtlRunLog]

BASE_COLUMNS = {
    "pid",
    "uid",
    "is_deleted",
    "created_at",
    "updated_at",
    "created_by",
    "updated_by",
}


def _table(model: type[BaseModel]) -> Table:
    # mypy 下 __table__ 型別為 FromClause,實際為 Table
    return cast(Table, model.__table__)


def _index_names(model: type[BaseModel]) -> set[str]:
    return {idx.name for idx in _table(model).indexes if idx.name is not None}


def _check_constraint_names(model: type[BaseModel]) -> set[str]:
    return {
        c.name
        for c in _table(model).constraints
        if isinstance(c, CheckConstraint) and isinstance(c.name, str)
    }


def _fk_targets(model: type[BaseModel]) -> set[str]:
    return {fk.target_fullname for fk in model.__table__.foreign_keys}


def test_table_names() -> None:
    assert User.__tablename__ == "users"
    assert EtlTable.__tablename__ == "etl_tables"
    assert EtlMapping.__tablename__ == "etl_mappings"
    assert Schedule.__tablename__ == "schedules"
    assert EtlRun.__tablename__ == "etl_runs"
    assert EtlRunLog.__tablename__ == "etl_run_logs"


def test_all_models_inherit_base_model_and_have_required_columns() -> None:
    """全表遵循 BaseModel 必備欄位 + 軟刪除。"""
    for model in ALL_MODELS:
        assert issubclass(model, BaseModel), model.__name__
        columns = set(model.__table__.columns.keys())
        missing = BASE_COLUMNS - columns
        assert not missing, f"{model.__name__} 缺必備欄位:{missing}"


def test_base_columns_constraints() -> None:
    """pid 內部主鍵 / uid 對外唯一 / is_deleted 預設 false。"""
    for model in ALL_MODELS:
        table = model.__table__
        assert table.columns["pid"].primary_key, model.__name__
        assert table.columns["uid"].unique, model.__name__
        assert table.columns["is_deleted"].nullable is False, model.__name__
        assert table.columns["created_by"].nullable is False, model.__name__
        assert table.columns["updated_by"].nullable is False, model.__name__


def test_users_columns_and_constraints() -> None:
    table = User.__table__
    assert table.columns["username"].nullable is False
    # 密碼只存雜湊;SSO-only 使用者可無本地密碼
    assert table.columns["password_hash"].nullable is True
    assert "password" not in table.columns  # 禁明文密碼欄
    assert table.columns["role"].nullable is False
    assert "ck_users_role" in _check_constraint_names(User)
    assert {"uq_users_username", "uq_users_sso_subject"} <= _index_names(User)


def test_users_username_unique_is_partial_index() -> None:
    """軟刪除後允許重建同帳號:username 唯一為 partial unique index。"""
    idx = next(i for i in _table(User).indexes if i.name == "uq_users_username")
    assert idx.unique
    assert idx.dialect_options["postgresql"]["where"] is not None


def test_etl_tables_columns() -> None:
    table = EtlTable.__table__
    for col in ("source_schema", "source_table", "target_schema", "target_table"):
        assert table.columns[col].nullable is False, col
    assert table.columns["is_enabled"].nullable is False
    assert "uq_etl_tables_source" in _index_names(EtlTable)


def test_etl_mappings_columns_and_fk() -> None:
    table = EtlMapping.__table__
    assert "etl_tables.pid" in _fk_targets(EtlMapping)
    assert table.columns["etl_table_pid"].nullable is False
    assert table.columns["source_column"].nullable is False
    assert table.columns["target_column"].nullable is False
    # 欄位 Comment 為契約必填(供 COMMENT ON COLUMN)
    assert table.columns["comment"].nullable is False
    assert table.columns["transform_type"].nullable is True
    assert "uq_etl_mappings_table_target" in _index_names(EtlMapping)


def test_schedules_columns_and_fk() -> None:
    table = Schedule.__table__
    assert table.columns["name"].nullable is False
    assert table.columns["cron_expr"].nullable is False
    assert table.columns["is_enabled"].nullable is False
    # NULL = 全部啟用表
    assert table.columns["etl_table_pid"].nullable is True
    assert "etl_tables.pid" in _fk_targets(Schedule)
    assert "uq_schedules_name" in _index_names(Schedule)


def test_etl_runs_columns_and_constraints() -> None:
    table = EtlRun.__table__
    assert table.columns["trigger_type"].nullable is False
    assert table.columns["status"].nullable is False
    assert table.columns["schedule_pid"].nullable is True
    assert table.columns["started_at"].nullable is True
    assert table.columns["finished_at"].nullable is True
    assert "schedules.pid" in _fk_targets(EtlRun)
    names = _check_constraint_names(EtlRun)
    assert {"ck_etl_runs_trigger_type", "ck_etl_runs_status"} <= names


def test_etl_run_logs_columns_and_fks() -> None:
    """逐表明細:筆數 / 耗時 / 狀態 / 錯誤含 stack trace。"""
    table = EtlRunLog.__table__
    assert table.columns["etl_run_pid"].nullable is False
    assert table.columns["etl_table_pid"].nullable is True
    assert table.columns["source_schema"].nullable is False
    assert table.columns["source_table"].nullable is False
    assert table.columns["row_count"].nullable is True
    assert table.columns["duration_ms"].nullable is True
    assert table.columns["error_message"].nullable is True
    assert table.columns["error_stack"].nullable is True
    assert {"etl_runs.pid", "etl_tables.pid"} <= _fk_targets(EtlRunLog)
    assert "ck_etl_run_logs_status" in _check_constraint_names(EtlRunLog)


def test_index_naming_convention() -> None:
    """索引 idx_{table}_* / 唯一鍵 uq_{table}_*(04-databases/00-overview 命名)。"""
    for model in ALL_MODELS:
        table = _table(model)
        table_name = table.name
        for idx in table.indexes:
            assert isinstance(idx, Index)
            assert idx.name is not None
            expected_prefix = (
                f"uq_{table_name}_" if idx.unique else f"idx_{table_name}_"
            )
            assert idx.name.startswith(expected_prefix), idx.name
