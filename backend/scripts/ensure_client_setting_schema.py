"""目標 RDS `client_setting` schema 冪等建置入口(v1.6.1 fixed AD-151)。

`ensure_client_setting_schema_on_target()` 原本只有測試檔呼叫,正式環境沒有任何建置入口
→ 新環境部署後 `client_setting` schema 不存在,權限管理端點全數 `UndefinedTable` 轉 500。
本腳本比照 `scripts/seed_semantic_mappings.py` 補上維運入口,列入部署 runbook:
**上站前(含測試站 / 正式站)對目標 RDS 跑一次**。

冪等:內部全為 `CREATE SCHEMA / TABLE / INDEX IF NOT EXISTS`,重跑不報錯、不刪除既有結構
(禁任何 DROP)。

連線沿用 `app.etl.reader.rds_database_url`(目標 RDS,`AWS_RDS_TARGET_DB`)。

用法(於 backend/ 目錄;需 `AWS_RDS_HOST/PORT/USER/PASSWORD/AWS_RDS_TARGET_DB` env):
    uv run python scripts/ensure_client_setting_schema.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 以 `python scripts/ensure_client_setting_schema.py` 直跑時,需把 backend/ 加入 sys.path
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import text  # noqa: E402

from app.etl.client_setting_schema import (  # noqa: E402
    client_setting_engine,
    ensure_client_setting_schema_on_target,
)
from app.models.client_setting import (  # noqa: E402
    CLIENT_SETTING_SCHEMA,
    CLIENT_SETTING_TABLES,
)

_TABLES_SQL = text(
    "SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"
)


async def run_ensure() -> list[str]:
    """執行冪等建置,回傳建置後實際存在的表名(排序;CLI 與測試共用入口)。"""
    await ensure_client_setting_schema_on_target()
    async with client_setting_engine() as engine, engine.connect() as conn:
        rows = (
            await conn.execute(_TABLES_SQL, {"schema": CLIENT_SETTING_SCHEMA})
        ).scalars().all()
    return sorted(str(row) for row in rows)


def main() -> int:
    tables = asyncio.run(run_ensure())
    missing = sorted(set(CLIENT_SETTING_TABLES) - set(tables))
    print(
        f"client_setting schema 建置完成:{CLIENT_SETTING_SCHEMA} 現有 {len(tables)} 張表"
        f"(預期 {len(CLIENT_SETTING_TABLES)} 張)"
    )
    print("表清單:" + ", ".join(tables))
    if missing:
        print("**缺表**:" + ", ".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
