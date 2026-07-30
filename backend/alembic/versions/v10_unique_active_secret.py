"""v1.6.0 scan AD-135 / AD-138:api_client_secrets 單一 active 密鑰 DB 兜底。

- 併發 rotate 可能繞過 repo 檢核產生同 client 多把 active → 先防禦性收斂既有重複
  (保留 created_at 最新者,同時間比 pid;其餘 UPDATE 為 retired,不刪列),
  再建 partial unique index `(api_client_user_pid) WHERE status='active' AND is_deleted=false`。
- 表 comment 由 v8 的雙鑰語意改為單一密鑰制(AD-138;v8 已套用禁回改,故於此修正)。
- downgrade 僅撤本次自建 index(CLAUDE.md round-trip 必要例外;不動資料與 comment)。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "v10"
down_revision: str | None = "v9"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TABLE = "api_client_secrets"
_INDEX = "uq_api_client_secrets_single_active"


def upgrade() -> None:
    # 1) 防禦性收斂:同 client 多把 active(未刪除)時,僅保留最新一把,其餘轉 retired
    op.execute(
        sa.text(
            """
            UPDATE api_client_secrets AS s
            SET status = 'retired'
            WHERE s.status = 'active'
              AND s.is_deleted = false
              AND EXISTS (
                SELECT 1
                FROM api_client_secrets AS newer
                WHERE newer.api_client_user_pid = s.api_client_user_pid
                  AND newer.status = 'active'
                  AND newer.is_deleted = false
                  AND (
                    newer.created_at > s.created_at
                    OR (newer.created_at = s.created_at AND newer.pid > s.pid)
                  )
              )
            """
        )
    )
    # 2) 單一 active 的 DB 層兜底(併發 rotate 繞過 repo 檢核時由此擋下)
    op.create_index(
        _INDEX,
        _TABLE,
        ["api_client_user_pid"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND is_deleted = false"),
        if_not_exists=True,
    )
    # 3) 表 comment 改單鑰語意(AD-138)
    op.execute(
        "COMMENT ON TABLE api_client_secrets IS "
        "'API Client 密鑰(單一密鑰制:同 client 恆一把 active,輪替即撤舊,只存 bcrypt 雜湊)"
        " / API client secrets (single active key per client; rotation retires the old one; "
        "bcrypt hash only)'"
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name=_TABLE, if_exists=True)
