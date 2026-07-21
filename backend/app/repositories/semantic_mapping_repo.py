"""semantic_mappings 副本表 repo(task-003,propose A5):RDS 語意映射的自有 DB 唯讀鏡像。

RDS `erp_metadata.semantic_mappings` 為唯一事實來源;本表由同步 job 單向整表重灌
(DELETE + bulk INSERT,單交易),**禁**任何寫入 API 反向寫回 RDS。

- `replace_all`:整表重灌,供 worker 同步步驟(`app/worker/tasks.py`)呼叫。
- `get_confirmed_map`:讀 confirmed 狀態映射(column_name → english_name;
  column_name='' 為表層級英文名),供 API / view 重生(task-005)消費。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.semantic_mapping import SemanticMapping


@dataclass(frozen=True)
class SemanticMappingRow:
    """RDS 來源一列(`erp_metadata.semantic_mappings`)欄位快照,供 `replace_all` 落地。"""

    table_name: str
    column_name: str
    english_name: str
    zh_name: str | None
    status: str
    source_updated_by: UUID | None
    source_updated_at: datetime | None


class SemanticMappingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def replace_all(
        self, rows: list[SemanticMappingRow], *, actor_uid: UUID
    ) -> int:
        """整表重灌(單交易 DELETE + bulk INSERT):副本 = RDS 來源全量。回傳寫入筆數。

        單向 RDS → 自有 DB;本方法為唯一寫入入口,禁增量 upsert(來源小表免增量)。
        DELETE + INSERT 同在本次呼叫的交易內以 commit 收尾,滿足「單交易」契約。
        """
        await self._db.execute(delete(SemanticMapping))
        self._db.add_all(
            [
                SemanticMapping(
                    uid=uuid4(),
                    table_name=row.table_name,
                    column_name=row.column_name,
                    english_name=row.english_name,
                    zh_name=row.zh_name,
                    status=row.status,
                    source_updated_by=row.source_updated_by,
                    source_updated_at=row.source_updated_at,
                    created_by=actor_uid,
                    updated_by=actor_uid,
                )
                for row in rows
            ]
        )
        await self._db.commit()
        return len(rows)

    async def get_confirmed_map(self, table_name: str) -> dict[str, str]:
        """讀指定表 confirmed 狀態映射:column_name → english_name。

        column_name=''(表層級映射)亦包含在內,由呼叫端依需求取用(如 view 重生
        用表層級英文名決定 view 名稱、用各欄英文名決定 view 欄別名)。
        """
        stmt = select(SemanticMapping.column_name, SemanticMapping.english_name).where(
            SemanticMapping.table_name == table_name,
            SemanticMapping.status == "confirmed",
            SemanticMapping.is_deleted.is_(False),
        )
        rows = (await self._db.execute(stmt)).all()
        return {str(column_name): str(english_name) for column_name, english_name in rows}
