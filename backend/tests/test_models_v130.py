"""v1.3.0 models 欄位斷言(純 metadata 檢查,不連 DB)。

rds_table_meta 新增增量同步基準(last_stat_ins/upd/del)與逐表排除旗標(sync_excluded)。
"""

import os

# app.core.db 於 import 時即建立 engine,測試不連 DB,僅需合法 URL 讓 Settings 可載入
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test"
)

from sqlalchemy import BigInteger  # noqa: E402

from app.models import RdsTableMeta  # noqa: E402


def test_v130_columns_exist() -> None:
    columns = RdsTableMeta.__table__.columns
    for name in ("last_stat_ins", "last_stat_upd", "last_stat_del", "sync_excluded"):
        assert name in columns, name


def test_stat_columns_nullable() -> None:
    columns = RdsTableMeta.__table__.columns
    for name in ("last_stat_ins", "last_stat_upd", "last_stat_del"):
        assert columns[name].nullable is True, name


def test_stat_columns_are_bigint() -> None:
    columns = RdsTableMeta.__table__.columns
    for name in ("last_stat_ins", "last_stat_upd", "last_stat_del"):
        assert isinstance(columns[name].type, BigInteger), name


def test_sync_excluded_not_null_with_server_default() -> None:
    col = RdsTableMeta.__table__.columns["sync_excluded"]
    assert col.nullable is False
    assert col.server_default is not None
