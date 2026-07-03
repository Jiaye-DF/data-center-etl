"""v1.1.0 核心資料表:users / etl_tables / etl_mappings / schedules / etl_runs / etl_run_logs。

只增不刪;downgrade 僅撤銷本次新增的表與索引。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "v1"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# downgrade 依 FK 依賴反序撤銷
_TABLES_IN_CREATE_ORDER = (
    "users",
    "etl_tables",
    "etl_mappings",
    "schedules",
    "etl_runs",
    "etl_run_logs",
)


def _base_columns() -> list[sa.Column]:
    """BaseModel 必備欄位(pid / uid / is_deleted / created_at / updated_at / created_by / updated_by)。"""
    return [
        sa.Column(
            "pid",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="內部主鍵(禁對外)/ Internal primary key (never exposed)",
        ),
        sa.Column(
            "uid",
            PG_UUID(as_uuid=True),
            nullable=False,
            comment="對外識別碼(UUID)/ External unique identifier (UUID)",
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="軟刪除旗標 / Soft-delete flag",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
            comment="建立時間(UTC+8)/ Created at (UTC+8)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
            comment="更新時間(UTC+8)/ Updated at (UTC+8)",
        ),
        sa.Column(
            "created_by",
            PG_UUID(as_uuid=True),
            nullable=False,
            comment="建立者(users.uid)/ Created by (users.uid)",
        ),
        sa.Column(
            "updated_by",
            PG_UUID(as_uuid=True),
            nullable=False,
            comment="最後更新者(users.uid)/ Updated by (users.uid)",
        ),
    ]


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────
    if not _has_table("users"):
        op.create_table(
            "users",
            *_base_columns(),
            sa.Column(
                "username",
                sa.String(length=100),
                nullable=False,
                comment="登入帳號 / Login username",
            ),
            sa.Column(
                "password_hash",
                sa.Text(),
                nullable=True,
                comment="密碼雜湊(bcrypt,禁明文)/ Password hash (bcrypt only)",
            ),
            sa.Column(
                "role",
                sa.String(length=20),
                server_default="viewer",
                nullable=False,
                comment="角色(admin/viewer)/ Role (admin/viewer)",
            ),
            sa.Column(
                "sso_subject",
                sa.String(length=255),
                nullable=True,
                comment="DF-SSO 對外識別碼(獨立欄位,禁作主鍵)/ DF-SSO external subject id",
            ),
            sa.PrimaryKeyConstraint("pid"),
            sa.UniqueConstraint("uid", name="uq_users_uid"),
            sa.CheckConstraint("role IN ('admin', 'viewer')", name="ck_users_role"),
            comment="使用者(本地帳密 + 角色 + SSO 對應)/ Users (local credential + role + SSO)",
        )
    op.create_index(
        "uq_users_username",
        "users",
        ["username"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        if_not_exists=True,
    )
    op.create_index(
        "uq_users_sso_subject",
        "users",
        ["sso_subject"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false AND sso_subject IS NOT NULL"),
        if_not_exists=True,
    )

    # ── etl_tables ─────────────────────────────────────────
    if not _has_table("etl_tables"):
        op.create_table(
            "etl_tables",
            *_base_columns(),
            sa.Column(
                "source_schema",
                sa.String(length=100),
                nullable=False,
                comment="來源 schema(如 DS)/ Source schema (e.g. DS)",
            ),
            sa.Column(
                "source_table",
                sa.String(length=200),
                nullable=False,
                comment="來源表名 / Source table name",
            ),
            sa.Column(
                "target_schema",
                sa.String(length=100),
                nullable=False,
                comment="目標 schema / Target schema",
            ),
            sa.Column(
                "target_table",
                sa.String(length=200),
                nullable=False,
                comment="目標表名 / Target table name",
            ),
            sa.Column(
                "is_enabled",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
                comment="是否啟用(停用表不處理)/ Enabled flag (disabled tables are skipped)",
            ),
            sa.Column(
                "description",
                sa.Text(),
                nullable=True,
                comment="表用途描述 / Table description",
            ),
            sa.PrimaryKeyConstraint("pid"),
            sa.UniqueConstraint("uid", name="uq_etl_tables_uid"),
            comment="ETL 表設定(來源/目標/啟用)/ ETL table config (source/target/enabled)",
        )
    op.create_index(
        "uq_etl_tables_source",
        "etl_tables",
        ["source_schema", "source_table"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        if_not_exists=True,
    )

    # ── etl_mappings ───────────────────────────────────────
    if not _has_table("etl_mappings"):
        op.create_table(
            "etl_mappings",
            *_base_columns(),
            sa.Column(
                "etl_table_pid",
                sa.BigInteger(),
                nullable=False,
                comment="所屬 ETL 表(etl_tables.pid)/ Parent ETL table (etl_tables.pid)",
            ),
            sa.Column(
                "source_column",
                sa.String(length=200),
                nullable=False,
                comment="來源欄名 / Source column name",
            ),
            sa.Column(
                "target_column",
                sa.String(length=200),
                nullable=False,
                comment="目標欄名 / Target column name",
            ),
            sa.Column(
                "transform_type",
                sa.String(length=50),
                nullable=True,
                comment="型別轉換規則(str/int/float,NULL 為不轉換)/ Transform rule (str/int/float)",
            ),
            sa.Column(
                "comment",
                sa.Text(),
                nullable=False,
                comment="欄位說明(產生 COMMENT ON COLUMN,契約非空)/ Column comment (must be non-empty)",
            ),
            sa.Column(
                "sort_order",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
                comment="欄位排序 / Column sort order",
            ),
            sa.PrimaryKeyConstraint("pid"),
            sa.UniqueConstraint("uid", name="uq_etl_mappings_uid"),
            sa.ForeignKeyConstraint(
                ["etl_table_pid"], ["etl_tables.pid"], name="fk_etl_mappings_etl_table"
            ),
            comment="ETL 欄位對照(含欄位 Comment)/ ETL column mapping (with column comments)",
        )
    op.create_index(
        "uq_etl_mappings_table_target",
        "etl_mappings",
        ["etl_table_pid", "target_column"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        if_not_exists=True,
    )
    op.create_index(
        "idx_etl_mappings_etl_table_pid",
        "etl_mappings",
        ["etl_table_pid"],
        if_not_exists=True,
    )

    # ── schedules ──────────────────────────────────────────
    if not _has_table("schedules"):
        op.create_table(
            "schedules",
            *_base_columns(),
            sa.Column(
                "name",
                sa.String(length=200),
                nullable=False,
                comment="排程名稱 / Schedule name",
            ),
            sa.Column(
                "cron_expr",
                sa.String(length=100),
                nullable=False,
                comment="cron 運算式(Asia/Taipei)/ Cron expression (Asia/Taipei)",
            ),
            sa.Column(
                "is_enabled",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
                comment="是否啟用 / Enabled flag",
            ),
            sa.Column(
                "etl_table_pid",
                sa.BigInteger(),
                nullable=True,
                comment="指定單表(NULL 為全部啟用表)/ Target ETL table (NULL = all enabled tables)",
            ),
            sa.Column(
                "description",
                sa.Text(),
                nullable=True,
                comment="排程描述 / Schedule description",
            ),
            sa.PrimaryKeyConstraint("pid"),
            sa.UniqueConstraint("uid", name="uq_schedules_uid"),
            sa.ForeignKeyConstraint(
                ["etl_table_pid"], ["etl_tables.pid"], name="fk_schedules_etl_table"
            ),
            comment="排程定義(cron + 啟停)/ Schedules (cron + enable/disable)",
        )
    op.create_index(
        "uq_schedules_name",
        "schedules",
        ["name"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        if_not_exists=True,
    )

    # ── etl_runs ───────────────────────────────────────────
    if not _has_table("etl_runs"):
        op.create_table(
            "etl_runs",
            *_base_columns(),
            sa.Column(
                "trigger_type",
                sa.String(length=20),
                nullable=False,
                comment="觸發方式(schedule/manual)/ Trigger type (schedule/manual)",
            ),
            sa.Column(
                "schedule_pid",
                sa.BigInteger(),
                nullable=True,
                comment="來源排程(手動觸發為 NULL)/ Source schedule (NULL when manual)",
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                server_default="pending",
                nullable=False,
                comment="執行狀態(pending/running/success/partial/failed)/ Run status",
            ),
            sa.Column(
                "started_at",
                sa.DateTime(),
                nullable=True,
                comment="開始時間(UTC+8)/ Started at (UTC+8)",
            ),
            sa.Column(
                "finished_at",
                sa.DateTime(),
                nullable=True,
                comment="結束時間(UTC+8)/ Finished at (UTC+8)",
            ),
            sa.Column(
                "total_tables",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
                comment="處理表總數 / Total tables processed",
            ),
            sa.Column(
                "success_tables",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
                comment="成功表數 / Succeeded tables",
            ),
            sa.Column(
                "failed_tables",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
                comment="失敗表數 / Failed tables",
            ),
            sa.Column(
                "error_message",
                sa.Text(),
                nullable=True,
                comment="整體錯誤訊息 / Overall error message",
            ),
            sa.PrimaryKeyConstraint("pid"),
            sa.UniqueConstraint("uid", name="uq_etl_runs_uid"),
            sa.ForeignKeyConstraint(
                ["schedule_pid"], ["schedules.pid"], name="fk_etl_runs_schedule"
            ),
            sa.CheckConstraint(
                "trigger_type IN ('schedule', 'manual')", name="ck_etl_runs_trigger_type"
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'running', 'success', 'partial', 'failed')",
                name="ck_etl_runs_status",
            ),
            comment="ETL 執行紀錄(一次執行)/ ETL runs (one execution per row)",
        )
    op.create_index("idx_etl_runs_status", "etl_runs", ["status"], if_not_exists=True)
    op.create_index("idx_etl_runs_started_at", "etl_runs", ["started_at"], if_not_exists=True)

    # ── etl_run_logs ───────────────────────────────────────
    if not _has_table("etl_run_logs"):
        op.create_table(
            "etl_run_logs",
            *_base_columns(),
            sa.Column(
                "etl_run_pid",
                sa.BigInteger(),
                nullable=False,
                comment="所屬執行(etl_runs.pid)/ Parent run (etl_runs.pid)",
            ),
            sa.Column(
                "etl_table_pid",
                sa.BigInteger(),
                nullable=True,
                comment="對應 ETL 表(設定被刪時保留 log 為 NULL)/ ETL table ref (nullable)",
            ),
            sa.Column(
                "source_schema",
                sa.String(length=100),
                nullable=False,
                comment="來源 schema(執行當下快照)/ Source schema snapshot",
            ),
            sa.Column(
                "source_table",
                sa.String(length=200),
                nullable=False,
                comment="來源表名(執行當下快照)/ Source table snapshot",
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                server_default="pending",
                nullable=False,
                comment="逐表狀態(pending/running/success/failed/skipped)/ Per-table status",
            ),
            sa.Column(
                "row_count",
                sa.BigInteger(),
                nullable=True,
                comment="處理筆數 / Rows processed",
            ),
            sa.Column(
                "duration_ms",
                sa.BigInteger(),
                nullable=True,
                comment="耗時(毫秒)/ Duration in milliseconds",
            ),
            sa.Column(
                "started_at",
                sa.DateTime(),
                nullable=True,
                comment="開始時間(UTC+8)/ Started at (UTC+8)",
            ),
            sa.Column(
                "finished_at",
                sa.DateTime(),
                nullable=True,
                comment="結束時間(UTC+8)/ Finished at (UTC+8)",
            ),
            sa.Column(
                "error_message",
                sa.Text(),
                nullable=True,
                comment="錯誤訊息 / Error message",
            ),
            sa.Column(
                "error_stack",
                sa.Text(),
                nullable=True,
                comment="錯誤 stack trace / Error stack trace",
            ),
            sa.PrimaryKeyConstraint("pid"),
            sa.UniqueConstraint("uid", name="uq_etl_run_logs_uid"),
            sa.ForeignKeyConstraint(
                ["etl_run_pid"], ["etl_runs.pid"], name="fk_etl_run_logs_etl_run"
            ),
            sa.ForeignKeyConstraint(
                ["etl_table_pid"], ["etl_tables.pid"], name="fk_etl_run_logs_etl_table"
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'running', 'success', 'failed', 'skipped')",
                name="ck_etl_run_logs_status",
            ),
            comment="ETL 逐表明細 log(筆數/耗時/錯誤含 stack trace)/ ETL per-table logs",
        )
    op.create_index(
        "idx_etl_run_logs_etl_run_pid", "etl_run_logs", ["etl_run_pid"], if_not_exists=True
    )
    op.create_index(
        "idx_etl_run_logs_etl_table_pid", "etl_run_logs", ["etl_table_pid"], if_not_exists=True
    )


def downgrade() -> None:
    # 僅撤銷本次新增(反依賴順序);索引隨表一併移除
    for table_name in reversed(_TABLES_IN_CREATE_ORDER):
        if _has_table(table_name):
            op.drop_table(table_name)
