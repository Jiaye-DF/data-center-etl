"""稽核紀錄(AuditService):登入成敗 / 設定變更 / 手動觸發等事件寫 audit_logs。

- 正常路徑:`AuditService(db).log(...)` 掛呼叫端 request session(隨 get_db 尾端 commit)
- 失敗路徑(呼叫端隨後 raise → get_db rollback):用 `log_detached(...)` 獨立連線
  立即 commit,稽核不被回滾波及
- repositories/audit_repo 不在本 task 檔案白名單 → 查詢暫落本 service(同 sso_service 前例)
"""

import logging
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogListResponse, AuditLogResponse

logger = logging.getLogger(__name__)

# 匿名事件(登入失敗等)的 created_by / updated_by 用全零 UUID 系統帳號
# (同 app/worker/tasks.py 的 SYSTEM_ACTOR_UID 約定;worker 模組含 broker 副作用,不 import)
SYSTEM_ACTOR_UID = UUID("00000000-0000-0000-0000-000000000000")


def _build_entry(
    *,
    action: str,
    actor_uid: UUID | None,
    actor_username: str | None,
    target_type: str | None,
    target_uid: UUID | None,
    detail: str | None,
) -> AuditLog:
    audit_by = actor_uid if actor_uid is not None else SYSTEM_ACTOR_UID
    return AuditLog(
        actor_uid=actor_uid,
        actor_username=actor_username,
        action=action,
        target_type=target_type,
        target_uid=target_uid,
        detail=detail,
        created_by=audit_by,
        updated_by=audit_by,
    )


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def log(
        self,
        *,
        action: str,
        actor_uid: UUID | None = None,
        actor_username: str | None = None,
        target_type: str | None = None,
        target_uid: UUID | None = None,
        detail: str | None = None,
    ) -> AuditLog:
        """寫一列稽核(掛呼叫端 session;隨 get_db 尾端 commit)。"""
        if actor_username is None and actor_uid is not None and actor_uid != SYSTEM_ACTOR_UID:
            actor_username = await self._resolve_username(actor_uid)
        entry = _build_entry(
            action=action,
            actor_uid=actor_uid,
            actor_username=actor_username,
            target_type=target_type,
            target_uid=target_uid,
            detail=detail,
        )
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def list_logs(
        self, *, page: int, page_size: int, action: str | None = None
    ) -> AuditLogListResponse:
        """稽核清單(分頁,最新在前;可選 action 過濾)。"""
        conditions: list[ColumnElement[bool]] = [AuditLog.is_deleted.is_(False)]
        if action is not None:
            conditions.append(AuditLog.action == action)
        total = (
            await self._db.execute(
                select(func.count()).select_from(AuditLog).where(*conditions)
            )
        ).scalar_one()
        stmt = (
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.pid.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        return AuditLogListResponse(
            items=[AuditLogResponse.model_validate(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def _resolve_username(self, actor_uid: UUID) -> str | None:
        stmt = select(User.username).where(User.uid == actor_uid, User.is_deleted.is_(False))
        return (await self._db.execute(stmt)).scalar_one_or_none()


async def log_detached(
    *,
    action: str,
    actor_uid: UUID | None = None,
    actor_username: str | None = None,
    target_type: str | None = None,
    target_uid: UUID | None = None,
    detail: str | None = None,
) -> None:
    """獨立 session 寫稽核並立即 commit(呼叫端隨後 raise 也不被 rollback 波及)。

    每次呼叫建獨立 NullPool engine:失敗類事件低頻,且避免與全域連線池
    跨 event loop 重用衝突(pytest-asyncio 每測試換 loop);
    稽核寫入失敗只記 application log,不得讓主流程(如登入 401)變 500。
    """
    try:
        # session timezone 對齊全域 engine(core/db.py;fixed.md §18),created_at 才是 +8 wall-clock
        engine = create_async_engine(
            get_settings().DATABASE_URL,
            poolclass=NullPool,
            connect_args={"server_settings": {"timezone": "Asia/Taipei"}},
        )
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add(
                    _build_entry(
                        action=action,
                        actor_uid=actor_uid,
                        actor_username=actor_username,
                        target_type=target_type,
                        target_uid=target_uid,
                        detail=detail,
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()
    except Exception:
        logger.exception("稽核寫入失敗(detached):action=%s", action)
