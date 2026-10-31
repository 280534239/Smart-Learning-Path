"""异步数据库连接与会话管理。"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """所有 SQLAlchemy 模型的基类。"""


async def get_db() -> AsyncIterator[AsyncSession]:
    """为请求提供独立数据库会话。"""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """创建当前已注册模型的数据库表。"""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
