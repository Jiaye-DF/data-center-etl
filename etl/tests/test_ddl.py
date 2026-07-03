"""ddl.build_column_comments / 引號化 helper 的純函式測試(不需連 DB)。"""

from __future__ import annotations

import pytest

try:  # Glue 上以 common.* 執行;fallback 供 repo 根以 etl.common.* 匯入
    from common.ddl import build_column_comments, quote_ident, quote_literal
except ImportError:  # pragma: no cover
    from etl.common.ddl import build_column_comments, quote_ident, quote_literal


def test_n_columns_produce_n_statements():
    """N 欄位 → 產生 N 條 COMMENT ON COLUMN。"""
    columns = ["id", "name", "created_at"]
    comments = {"id": "主鍵", "name": "名稱", "created_at": "建立時間"}
    stmts = build_column_comments("users", columns, comments, schema="etl")
    assert len(stmts) == len(columns)
    assert all(s.startswith("COMMENT ON COLUMN ") for s in stmts)
    assert stmts[0] == 'COMMENT ON COLUMN "etl"."users"."id" IS \'主鍵\';'


def test_missing_comment_raises():
    """缺 comment 的欄位會 raise,訊息列出缺哪些欄。"""
    columns = ["id", "name", "email"]
    comments = {"id": "主鍵"}  # 缺 name / email
    with pytest.raises(ValueError) as exc:
        build_column_comments("users", columns, comments)
    assert "name" in str(exc.value)
    assert "email" in str(exc.value)


def test_blank_comment_treated_as_missing():
    """空字串 / 空白描述視同缺席,會 raise。"""
    columns = ["id"]
    with pytest.raises(ValueError):
        build_column_comments("users", columns, {"id": "   "})


def test_single_quote_in_comment_escaped():
    """comment 內容含單引號 → 跳脫為 ''。"""
    columns = ["note"]
    comments = {"note": "it's a 'test'"}
    stmts = build_column_comments("t", columns, comments, schema="public")
    assert stmts[0] == 'COMMENT ON COLUMN "public"."t"."note" IS \'it\'\'s a \'\'test\'\'\';'


def test_double_quote_in_identifier_escaped():
    """識別字含雙引號 → 跳脫為 ""。"""
    assert quote_ident('we"ird') == '"we""ird"'


def test_illegal_identifier_raises():
    """空識別字 / 含控制字元的識別字會 raise。"""
    with pytest.raises(ValueError):
        quote_ident("")
    with pytest.raises(ValueError):
        quote_ident("bad\nname")


def test_quote_literal_escapes_single_quote():
    assert quote_literal("a'b") == "'a''b'"
