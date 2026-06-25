"""
数据库会话模块，负责创建和管理异步数据库会话。
创建异步数据库引擎、异步会话工厂，并提供 FastAPI 可注入的 `get_session()` 函数。
每个请求获得独立的数据库会话，请求结束后自动释放连接资源。
"""

from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _ensure_database_file_dir(database_url: str) -> None:
    """SQLite 不会自动创建数据库文件的父目录，需在建立连接前手动确保其存在。

    仅对基于文件的 SQLite URL 生效；内存数据库与其他数据库协议不做处理，
    避免对相对路径（如 ``./data/github_sentinel.db``）导致的启动失败。
    """
    url = make_url(database_url)
    # url.database 对 SQLite 即数据库文件路径；内存数据库为 ":memory:"，无路径时为 None
    if not url.drivername.startswith("sqlite"):
        return
    database = url.database
    if not database or database == ":memory:":
        return
    # [假设] database_url 中的相对路径以进程当前工作目录为基准，
    # 与 SQLAlchemy 建立连接时的解析行为一致
    parent_dir = Path(database).expanduser().resolve().parent
    parent_dir.mkdir(parents=True, exist_ok=True)


# 在创建引擎前确保 SQLite 文件目录存在，否则连接初始化会抛
# sqlite3.OperationalError: unable to open database file
_ensure_database_file_dir(settings.database_url)

engine = create_async_engine(settings.database_url, future=True)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    """为每个新 SQLite 连接设置并发友好的 PRAGMA。

    背景：SQLite 默认 ``busy_timeout=0``，任何写锁冲突都会立即抛
    ``database is locked``，而 FastAPI 中间件对每个请求（含静态资源）
    都会校验会话，并发写极易冲突。

    - ``journal_mode=WAL``：写入不阻塞读、读不阻塞写，显著降低锁争用。
    - ``busy_timeout=5000``：写锁被占时最多等待 5 秒再失败，而非立即抛错。
    - ``synchronous=NORMAL``：WAL 模式下的安全档位，兼顾一致性与性能。

    通过 URL drivername 判断是否 SQLite，而非 dbapi 连接的类——
    aiosqlite 的连接被 SQLAlchemy 用 AsyncAdapt 包装，模块名不再是 ``sqlite3``。
    """
    if not settings.database_url.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """为每个 FastAPI 请求提供独立异步数据库会话。"""
    # 每个请求获得独立 session，请求结束后自动释放连接资源。
    async with AsyncSessionLocal() as session:
        yield session
