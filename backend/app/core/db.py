from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    # DB session timezone 對齊 Asia/Taipei(05-timezone.md):
    # server_default=func.now() 類欄位改寫 +8 wall-clock,
    # 與 Python now_tw() 寫入的欄位一致(fixed.md §18)
    connect_args={"server_settings": {"timezone": "Asia/Taipei"}},
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
