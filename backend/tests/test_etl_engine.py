"""engine.run_etl 編排測試:以 in-memory fake(reader / writer / store)驗證,不連真 RDS。

涵蓋:停用表 skipped、單表失敗續跑且 log 含 stack trace、
每欄位 comment 缺值 fail、機密遮罩、env fail-fast。
"""

import os

# app.core.db 於 import 時建立 engine;測試不連 DB,僅需合法 URL 讓 Settings 可載入
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

from collections.abc import Mapping, Sequence  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402

from app.etl.engine import EtlTableConfig, run_etl  # noqa: E402
from app.etl.reader import rds_database_url  # noqa: E402
from app.etl.transforms import ColumnMapping  # noqa: E402
from app.etl.writer import column_sql_type  # noqa: E402

# ---------------------------------------------------------------------------
# Fakes(結構相容 engine 的 SourceReader / TargetWriter / RunStore Protocol)
# ---------------------------------------------------------------------------


class FakeReader:
    """以 (schema, table) 對照回傳預置列;可指定失敗表模擬讀取例外。"""

    def __init__(
        self,
        data: dict[tuple[str, str], list[dict[str, Any]]],
        fail_tables: set[tuple[str, str]] | None = None,
        fail_message: str = "來源讀取失敗",
    ) -> None:
        self._data = data
        self._fail_tables = fail_tables or set()
        self._fail_message = fail_message
        self.calls: list[tuple[str, str]] = []

    async def fetch_rows(
        self, schema: str, table: str, columns: Sequence[str]
    ) -> list[dict[str, Any]]:
        self.calls.append((schema, table))
        if (schema, table) in self._fail_tables:
            raise RuntimeError(f"{self._fail_message}:{schema}.{table}")
        rows = self._data.get((schema, table), [])
        return [{col: row.get(col) for col in columns} for row in rows]


class FakeWriter:
    """記錄每次寫入內容供斷言。"""

    def __init__(self) -> None:
        self.writes: list[dict[str, Any]] = []

    async def write_table(
        self,
        *,
        schema: str,
        table: str,
        columns: Sequence[str],
        column_types: Mapping[str, str | None],
        rows: Sequence[Mapping[str, Any]],
        comment_statements: Sequence[str],
    ) -> int:
        self.writes.append(
            {
                "schema": schema,
                "table": table,
                "columns": list(columns),
                "column_types": dict(column_types),
                "rows": [dict(row) for row in rows],
                "comment_statements": list(comment_statements),
            }
        )
        return len(rows)


class FakeRunStore:
    """in-memory etl_runs / etl_run_logs,結構對齊 DbRunStore 寫入欄位。"""

    def __init__(self) -> None:
        self.run: dict[str, Any] = {}
        self.logs: list[dict[str, Any]] = []

    async def create_run(self, *, trigger_type: str, schedule_pid: int | None) -> int:
        self.run = {
            "trigger_type": trigger_type,
            "schedule_pid": schedule_pid,
            "status": "running",
        }
        return 1

    async def start_table_log(self, *, run_pid: int, config: EtlTableConfig) -> int:
        self.logs.append(
            {
                "run_pid": run_pid,
                "source_schema": config.source_schema,
                "source_table": config.source_table,
                "status": "running",
            }
        )
        return len(self.logs)  # 1-based log pid

    async def finish_table_log(
        self,
        log_pid: int,
        *,
        status: str,
        row_count: int | None,
        duration_ms: int | None,
        error_message: str | None,
        error_stack: str | None,
    ) -> None:
        self.logs[log_pid - 1].update(
            {
                "status": status,
                "row_count": row_count,
                "duration_ms": duration_ms,
                "error_message": error_message,
                "error_stack": error_stack,
            }
        )

    async def add_skipped_log(self, *, run_pid: int, config: EtlTableConfig) -> None:
        self.logs.append(
            {
                "run_pid": run_pid,
                "source_schema": config.source_schema,
                "source_table": config.source_table,
                "status": "skipped",
            }
        )

    async def finish_run(
        self,
        run_pid: int,
        *,
        status: str,
        total_tables: int,
        success_tables: int,
        failed_tables: int,
        error_message: str | None,
    ) -> None:
        self.run.update(
            {
                "status": status,
                "total_tables": total_tables,
                "success_tables": success_tables,
                "failed_tables": failed_tables,
                "error_message": error_message,
            }
        )


def _gat_config(*, is_enabled: bool = True) -> EtlTableConfig:
    """DS.GAT_FILE 設定(對照 v1.0.0 ds.yaml 欄位與尾碼型別)。"""
    return EtlTableConfig(
        etl_table_pid=1,
        source_schema="DS",
        source_table="GAT_FILE",
        target_schema="DS",
        target_table="GAT_FILE",
        is_enabled=is_enabled,
        mappings=(
            ColumnMapping("GAT_NO", "GAT_NO", "str", "單據編號(主鍵,字串)"),
            ColumnMapping("GAT_QTY", "GAT_QTY", "int", "數量(整數)"),
            ColumnMapping("GAT_AMT", "GAT_AMT", "float", "金額(浮點)"),
        ),
    )


def _gam_config() -> EtlTableConfig:
    """DS.GAM_FILE 單來源設定(對照 v1.0.0 ds.yaml)。"""
    return EtlTableConfig(
        etl_table_pid=5,
        source_schema="DS",
        source_table="GAM_FILE",
        target_schema="DS",
        target_table="GAM_FILE",
        is_enabled=True,
        mappings=(
            ColumnMapping("GAM_ID", "GAM_ID", "int", "主檔識別碼(主鍵,整數)"),
            ColumnMapping("GAM_NAME", "GAM_NAME", "str", "名稱(字串)"),
        ),
    )


def _m2201_config() -> EtlTableConfig:
    """M2201 多來源設定(對照 v1.0.0 m2201.yaml 子集 + fixed.md §2 字串約定)。"""
    return EtlTableConfig(
        etl_table_pid=2,
        source_schema="DS",
        source_table="GAT_FILE,GAQ_FILE",
        target_schema="M2201",
        target_table="M2201",
        is_enabled=True,
        mappings=(
            ColumnMapping("GAT_FILE.GAT_NO", "DOC_NO", "str", "單據編號(主鍵,字串)"),
            ColumnMapping("GAQ_FILE.GAQ_PRICE", "UNIT_PRICE", "float", "單價(浮點)"),
        ),
    )


# ---------------------------------------------------------------------------
# 正常路徑
# ---------------------------------------------------------------------------


async def test_run_success_transforms_and_logs() -> None:
    reader = FakeReader(
        {
            ("DS", "GAT_FILE"): [
                {"GAT_NO": " A1 ", "GAT_QTY": "3", "GAT_AMT": "1.5"},
                {"GAT_NO": "A2", "GAT_QTY": "null", "GAT_AMT": "2"},
            ],
            ("DS", "GAQ_FILE"): [
                {"GAQ_PRICE": "9.9"},
                {"GAQ_PRICE": "5"},
            ],
        }
    )
    writer = FakeWriter()
    store = FakeRunStore()

    result = await run_etl(
        [_gat_config(), _m2201_config()], reader=reader, writer=writer, store=store
    )

    assert result.status == "success"
    assert (result.total_tables, result.success_tables, result.failed_tables) == (2, 2, 0)
    assert store.run["status"] == "success"
    assert store.run["error_message"] is None

    # 轉換結果與 v1.0.0 行為一致(trim / null 正規化 / 型別)
    assert writer.writes[0]["rows"] == [
        {"GAT_NO": "A1", "GAT_QTY": 3, "GAT_AMT": 1.5},
        {"GAT_NO": "A2", "GAT_QTY": None, "GAT_AMT": 2.0},
    ]
    # 多來源欄位對映(GAT_FILE + GAQ_FILE → M2201,fixed.md §2 約定)
    assert writer.writes[1]["rows"] == [
        {"DOC_NO": "A1", "UNIT_PRICE": 9.9},
        {"DOC_NO": "A2", "UNIT_PRICE": 5.0},
    ]
    # 每欄位 comment 非空:N 欄 → N 條 COMMENT ON COLUMN
    assert len(writer.writes[0]["comment_statements"]) == 3
    assert (
        "COMMENT ON COLUMN \"M2201\".\"M2201\".\"DOC_NO\" IS '單據編號(主鍵,字串)';"
        in writer.writes[1]["comment_statements"]
    )

    # 逐表詳細 log:筆數 / 耗時 / 狀態
    assert [log["status"] for log in store.logs] == ["success", "success"]
    assert store.logs[0]["row_count"] == 2
    assert store.logs[1]["row_count"] == 2
    for log in store.logs:
        assert isinstance(log["duration_ms"], int)
        assert log["duration_ms"] >= 0
        assert log["error_stack"] is None


# ---------------------------------------------------------------------------
# 多來源合併(fixed.md §2 約定;佔位語意對齊 v1.0.0 m2201_job)
# ---------------------------------------------------------------------------


async def test_multi_source_zip_merge_fills_missing_rows_with_none() -> None:
    """多來源以列位置並排合併;短表缺列補 None。"""
    reader = FakeReader(
        {
            ("DS", "GAT_FILE"): [{"GAT_NO": "A1"}, {"GAT_NO": "A2"}],
            ("DS", "GAQ_FILE"): [{"GAQ_PRICE": "1.5"}],
        }
    )
    writer = FakeWriter()
    store = FakeRunStore()

    result = await run_etl([_m2201_config()], reader=reader, writer=writer, store=store)

    assert result.status == "success"
    assert writer.writes[0]["rows"] == [
        {"DOC_NO": "A1", "UNIT_PRICE": 1.5},
        {"DOC_NO": "A2", "UNIT_PRICE": None},
    ]
    # 各來源表各讀一次,且只讀該表負責的欄
    assert reader.calls == [("DS", "GAT_FILE"), ("DS", "GAQ_FILE")]


async def test_multi_source_requires_qualified_source_column() -> None:
    """多來源表的 mapping 來源欄未帶 <來源表>. 前綴 → 該表 fail(不靜默)。"""
    config = EtlTableConfig(
        etl_table_pid=6,
        source_schema="DS",
        source_table="GAT_FILE,GAQ_FILE",
        target_schema="M2201",
        target_table="M2201",
        is_enabled=True,
        mappings=(ColumnMapping("GAT_NO", "DOC_NO", "str", "單據編號(主鍵,字串)"),),
    )
    store = FakeRunStore()

    result = await run_etl(
        [config], reader=FakeReader({}), writer=FakeWriter(), store=store
    )

    assert result.status == "failed"
    assert "<來源表>.<欄名>" in store.logs[0]["error_message"]


# ---------------------------------------------------------------------------
# 停用表 skipped
# ---------------------------------------------------------------------------


async def test_disabled_table_is_skipped_with_log() -> None:
    reader = FakeReader({("DS", "GAM_FILE"): [{"GAM_ID": "1", "GAM_NAME": "x"}]})
    writer = FakeWriter()
    store = FakeRunStore()

    result = await run_etl(
        [_gat_config(is_enabled=False), _gam_config()],
        reader=reader,
        writer=writer,
        store=store,
    )

    assert result.status == "success"
    assert result.skipped_tables == 1
    # 停用表:log 標 skipped,且未讀取來源、未寫入目標
    skipped = [log for log in store.logs if log["status"] == "skipped"]
    assert len(skipped) == 1
    assert skipped[0]["source_table"] == "GAT_FILE"
    assert ("DS", "GAT_FILE") not in reader.calls
    assert [w["table"] for w in writer.writes] == ["GAM_FILE"]


# ---------------------------------------------------------------------------
# 單表失敗續跑 + stack trace
# ---------------------------------------------------------------------------


async def test_single_table_failure_continues_and_logs_stack_trace() -> None:
    reader = FakeReader(
        {("DS", "GAM_FILE"): [{"GAM_ID": "1", "GAM_NAME": "x"}]},
        fail_tables={("DS", "GAT_FILE")},
    )
    writer = FakeWriter()
    store = FakeRunStore()

    result = await run_etl(
        [_gat_config(), _gam_config()], reader=reader, writer=writer, store=store
    )

    # 單表失敗不中斷:第二表照跑成功,run 總狀態 failed
    assert result.status == "failed"
    assert (result.success_tables, result.failed_tables) == (1, 1)
    assert store.run["status"] == "failed"
    assert store.run["error_message"] == "1 表失敗"

    failed_log = next(log for log in store.logs if log["status"] == "failed")
    assert failed_log["source_table"] == "GAT_FILE"
    assert "來源讀取失敗" in failed_log["error_message"]
    # 詳細 log 含完整 stack trace
    assert "Traceback" in failed_log["error_stack"]
    assert "RuntimeError" in failed_log["error_stack"]

    success_log = next(log for log in store.logs if log["status"] == "success")
    assert success_log["source_table"] == "GAM_FILE"
    assert [w["table"] for w in writer.writes] == ["GAM_FILE"]


# ---------------------------------------------------------------------------
# comment 缺值 fail(不靜默)
# ---------------------------------------------------------------------------


async def test_missing_column_comment_fails_table_before_write() -> None:
    config = EtlTableConfig(
        etl_table_pid=3,
        source_schema="DS",
        source_table="GAM_FILE",
        target_schema="DS",
        target_table="GAM_FILE",
        is_enabled=True,
        mappings=(
            ColumnMapping("GAM_ID", "GAM_ID", "int", "主檔識別碼(主鍵,整數)"),
            ColumnMapping("GAM_NAME", "GAM_NAME", "str", ""),  # comment 空 → 須 fail
        ),
    )
    reader = FakeReader({("DS", "GAM_FILE"): [{"GAM_ID": "1", "GAM_NAME": "x"}]})
    writer = FakeWriter()
    store = FakeRunStore()

    result = await run_etl([config], reader=reader, writer=writer, store=store)

    assert result.status == "failed"
    failed_log = store.logs[0]
    assert failed_log["status"] == "failed"
    assert "GAM_NAME" in failed_log["error_message"]
    # comment 驗證先於讀寫:來源未讀、目標未寫
    assert reader.calls == []
    assert writer.writes == []


async def test_empty_mappings_fails_table() -> None:
    config = EtlTableConfig(
        etl_table_pid=4,
        source_schema="DS",
        source_table="EMPTY_TBL",
        target_schema="DS",
        target_table="EMPTY_TBL",
        is_enabled=True,
        mappings=(),
    )
    store = FakeRunStore()
    result = await run_etl([config], reader=FakeReader({}), writer=FakeWriter(), store=store)
    assert result.status == "failed"
    assert "無欄位 mapping" in store.logs[0]["error_message"]


# ---------------------------------------------------------------------------
# 機密遮罩(02-secrets.md § Log / error 過濾)
# ---------------------------------------------------------------------------


async def test_db_password_is_masked_in_error_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "s3cret-pw-value"
    monkeypatch.setenv("AWS_RDS_PASSWORD", secret)
    reader = FakeReader(
        {}, fail_tables={("DS", "GAT_FILE")}, fail_message=f"auth failed {secret} at"
    )
    store = FakeRunStore()

    await run_etl([_gat_config()], reader=reader, writer=FakeWriter(), store=store)

    failed_log = store.logs[0]
    assert secret not in failed_log["error_message"]
    assert secret not in failed_log["error_stack"]
    assert "****" in failed_log["error_message"]


# ---------------------------------------------------------------------------
# 連線 env fail-fast(缺值即 raise,訊息不含值)
# ---------------------------------------------------------------------------


def test_rds_database_url_fail_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("HOST", "PORT", "USER", "PASSWORD", "SOURCE_DB"):
        monkeypatch.delenv(f"AWS_RDS_{key}", raising=False)
    with pytest.raises(RuntimeError, match="AWS_RDS_HOST"):
        rds_database_url("AWS_RDS_SOURCE_DB")


def test_rds_database_url_builds_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_RDS_HOST", "db.local")
    monkeypatch.setenv("AWS_RDS_PORT", "5433")
    monkeypatch.setenv("AWS_RDS_USER", "etl_user")
    monkeypatch.setenv("AWS_RDS_PASSWORD", "p@ss w")
    # 來源/目標共用連線組,僅 database env 不同
    monkeypatch.setenv("AWS_RDS_SOURCE_DB", "erp_migration_test")
    monkeypatch.setenv("AWS_RDS_TARGET_DB", "erp_etl_hub_test")
    url = rds_database_url("AWS_RDS_SOURCE_DB")
    # 帳密 URL-encode 後進 URL;host / port / db 名正確
    assert url == "postgresql+asyncpg://etl_user:p%40ss+w@db.local:5433/erp_migration_test"
    target_url = rds_database_url("AWS_RDS_TARGET_DB")
    assert target_url.endswith("/erp_etl_hub_test")


def test_column_sql_type_mapping() -> None:
    assert column_sql_type("int") == "BIGINT"
    assert column_sql_type("float") == "DOUBLE PRECISION"
    assert column_sql_type("str") == "TEXT"
    assert column_sql_type(None) == "TEXT"
    assert column_sql_type("unknown") == "TEXT"
