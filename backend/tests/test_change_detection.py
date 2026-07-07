"""變動偵測引擎測試:stat_changed 純比對語意 + rows_to_stats / fetch_source_stats 轉換。

以 fake source engine 記錄執行的 SQL 並回傳假列,不連真 RDS。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.etl.mirror import MirrorEngine, TableStat, rows_to_stats, stat_changed

# ---------------------------------------------------------------------------
# stat_changed:純比對語意
# ---------------------------------------------------------------------------


def test_stat_changed_baseline_none_is_changed() -> None:
    # 首次上線 / 來源新表,尚無基準 → 視為變動
    current = TableStat(n_tup_ins=0, n_tup_upd=0, n_tup_del=0)
    assert stat_changed(current, None) is True


def test_stat_changed_counter_increased_is_changed() -> None:
    baseline = TableStat(n_tup_ins=10, n_tup_upd=5, n_tup_del=2)
    # ins 增加(有新增)
    assert stat_changed(TableStat(11, 5, 2), baseline) is True
    # upd 增加(有修改)
    assert stat_changed(TableStat(10, 6, 2), baseline) is True
    # del 增加(有刪除)
    assert stat_changed(TableStat(10, 5, 3), baseline) is True


def test_stat_changed_counter_decreased_is_changed() -> None:
    # 計數器倒退(來源重啟 / crash / pg_stat_reset 歸零)保守亦視為變動
    baseline = TableStat(n_tup_ins=10, n_tup_upd=5, n_tup_del=2)
    assert stat_changed(TableStat(9, 5, 2), baseline) is True
    assert stat_changed(TableStat(0, 0, 0), baseline) is True


def test_stat_changed_equal_is_not_changed() -> None:
    # 三者皆相等 → 未變動,本輪跳過
    baseline = TableStat(n_tup_ins=10, n_tup_upd=5, n_tup_del=2)
    assert stat_changed(TableStat(10, 5, 2), baseline) is False


# ---------------------------------------------------------------------------
# rows_to_stats:轉換 + counter None 落 0
# ---------------------------------------------------------------------------


def test_rows_to_stats_maps_two_tables() -> None:
    rows = [
        {"schema": "DS", "name": "AAA_FILE", "n_tup_ins": 3, "n_tup_upd": 1, "n_tup_del": 0},
        {"schema": "M2201", "name": "M2201", "n_tup_ins": 100, "n_tup_upd": 20, "n_tup_del": 5},
    ]
    result = rows_to_stats(rows)
    assert result == {
        ("DS", "AAA_FILE"): TableStat(3, 1, 0),
        ("M2201", "M2201"): TableStat(100, 20, 5),
    }


def test_rows_to_stats_none_counter_falls_to_zero() -> None:
    rows = [
        {"schema": "DS", "name": "EMPTY", "n_tup_ins": None, "n_tup_upd": None, "n_tup_del": None},
    ]
    result = rows_to_stats(rows)
    assert result == {("DS", "EMPTY"): TableStat(0, 0, 0)}


# ---------------------------------------------------------------------------
# fetch_source_stats:以 fake source engine 驗證整條轉換
# ---------------------------------------------------------------------------


class _FakeMappings:
    def __init__(self, rows: Sequence[Any]) -> None:
        self._rows = list(rows)

    def all(self) -> list[Any]:
        return self._rows


class _FakeResult:
    def __init__(self, rows: Sequence[Any]) -> None:
        self._rows = list(rows)

    def mappings(self) -> _FakeMappings:
        return _FakeMappings(self._rows)


class _FakeConn:
    def __init__(self, rows: Sequence[Any]) -> None:
        self._rows = rows
        self.executed: list[str] = []

    async def __aenter__(self) -> _FakeConn:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def execute(self, sql: Any, params: Any = None) -> _FakeResult:
        self.executed.append(str(sql))
        return _FakeResult(self._rows)


class _FakeEngine:
    def __init__(self, rows: Sequence[Any]) -> None:
        self.conn = _FakeConn(rows)

    def connect(self) -> _FakeConn:
        return self.conn


async def test_fetch_source_stats_returns_stat_dict() -> None:
    rows = [
        {"schema": "DS", "name": "AAA_FILE", "n_tup_ins": 3, "n_tup_upd": 1, "n_tup_del": 0},
        {"schema": "M2201", "name": "M2201", "n_tup_ins": None, "n_tup_upd": 2, "n_tup_del": 0},
    ]
    engine = _FakeEngine(rows)
    mirror = MirrorEngine()
    # 注入 fake source engine(避免建立真 RDS 連線)
    mirror._source_engine_obj = engine  # type: ignore[assignment]

    result = await mirror.fetch_source_stats()

    assert result == {
        ("DS", "AAA_FILE"): TableStat(3, 1, 0),
        ("M2201", "M2201"): TableStat(0, 2, 0),  # counter None → 0
    }
    # 確實查了 pg_stat_user_tables(零掃表)
    assert any("pg_stat_user_tables" in sql for sql in engine.conn.executed)
