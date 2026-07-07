"""v1.3.1 schedules 一表一排程欄位 / 索引斷言(純 metadata 檢查,不連 DB)。"""

import os

# app.core.db 於 import 時即建立 engine,測試不連 DB,僅需合法 URL 讓 Settings 可載入
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test"
)

from app.models import Schedule  # noqa: E402


def test_source_columns_exist_and_nullable() -> None:
    """source_schema / source_table 存在且可空。"""
    table = Schedule.__table__
    for col in ("source_schema", "source_table"):
        assert col in table.columns, col
        assert table.columns[col].nullable is True, col


def test_etl_table_pid_retained() -> None:
    """etl_table_pid 欄保留(deprecated 但未移除)。"""
    assert "etl_table_pid" in Schedule.__table__.columns


def test_partial_unique_index_on_source_table() -> None:
    """partial unique index uq_schedules_source_table 於未刪除範圍。"""
    target_name = "uq_schedules_source_table"
    idx = next(i for i in Schedule.__table__.indexes if i.name == target_name)
    assert idx.unique
    assert idx.dialect_options["postgresql"]["where"] is not None
    assert {c.name for c in idx.columns} == {"source_schema", "source_table"}
