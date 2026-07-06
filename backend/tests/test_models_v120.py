"""v1.2.0 models 欄位 / 約束斷言(純 metadata 檢查,不連 DB)。"""

import os

# app.core.db 於 import 時即建立 engine,測試不連 DB,僅需合法 URL 讓 Settings 可載入
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test"
)

from sqlalchemy import CheckConstraint, Index  # noqa: E402

from app.models import Dataset, RdsTableMeta  # noqa: E402


def _index_names() -> set[str]:
    return {idx.name for idx in RdsTableMeta.__table__.indexes if idx.name is not None}


def _check_constraint_names() -> set[str]:
    return {
        c.name
        for c in RdsTableMeta.__table__.constraints
        if isinstance(c, CheckConstraint) and isinstance(c.name, str)
    }


def test_table_name() -> None:
    assert RdsTableMeta.__tablename__ == "rds_table_meta"


def test_has_base_columns() -> None:
    """遵循 BaseModel 必備欄位(pid/uid/is_deleted/created_at/updated_at/created_by/updated_by)。"""
    columns = set(RdsTableMeta.__table__.columns.keys())
    base_columns = {
        "pid",
        "uid",
        "is_deleted",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    }
    assert not (base_columns - columns)
    table = RdsTableMeta.__table__
    assert table.columns["pid"].primary_key
    assert table.columns["uid"].unique
    assert table.columns["is_deleted"].nullable is False


def test_dataset_str_enum_values() -> None:
    """dataset 為 StrEnum,值限定 source / target。"""
    assert set(Dataset) == {Dataset.SOURCE, Dataset.TARGET}
    assert Dataset.SOURCE == "source"
    assert Dataset.TARGET == "target"


def test_dataset_check_constraint() -> None:
    assert "ck_rds_table_meta_dataset" in _check_constraint_names()


def test_business_name_column_nullable() -> None:
    """business_name 可空(GAT_FILE JOIN 快照,task-002 才寫入)。"""
    table = RdsTableMeta.__table__
    assert table.columns["business_name"].nullable is True


def test_required_columns() -> None:
    table = RdsTableMeta.__table__
    for col in ("dataset", "schema_name", "table_name", "column_count", "row_count"):
        assert table.columns[col].nullable is False, col
    for col in ("business_name", "snapshot_at", "last_synced_at", "last_transformed_at"):
        assert table.columns[col].nullable is True, col


def test_unique_key_is_partial_index_on_dataset_schema_table() -> None:
    """唯一鍵 (dataset, schema_name, table_name) 於未刪除範圍(供 upsert)。"""
    target_name = "uq_rds_table_meta_dataset_schema_table"
    idx = next(i for i in RdsTableMeta.__table__.indexes if i.name == target_name)
    assert idx.unique
    assert idx.dialect_options["postgresql"]["where"] is not None
    assert {c.name for c in idx.columns} == {"dataset", "schema_name", "table_name"}


def test_index_naming_convention() -> None:
    """索引 idx_{table}_* / 唯一鍵 uq_{table}_*(04-databases/00-overview 命名)。"""
    table = RdsTableMeta.__table__
    for idx in table.indexes:
        assert isinstance(idx, Index)
        assert idx.name is not None
        expected_prefix = f"uq_{table.name}_" if idx.unique else f"idx_{table.name}_"
        assert idx.name.startswith(expected_prefix), idx.name
