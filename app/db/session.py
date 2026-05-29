"""
数据库会话模块，负责创建和管理异步数据库会话。
创建异步数据库引擎、异步会话工厂，并提供 FastAPI 可注入的 `get_session()` 函数。
每个请求获得独立的数据库会话，请求结束后自动释放连接资源。
"""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """为每个 FastAPI 请求提供独立异步数据库会话。"""
    # 每个请求获得独立 session，请求结束后自动释放连接资源。
    async with AsyncSessionLocal() as session:
        yield session
