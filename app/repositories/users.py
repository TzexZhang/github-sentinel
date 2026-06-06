from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import User, UserSession
from app.services.auth import hash_password, hash_session_token, session_expiry, verify_password


async def create_user(
    session: AsyncSession,
    username: str,
    password: str,
    display_name: str | None = None,
    is_admin: bool = False,
) -> User:
    """创建本地用户并保存加密后的密码哈希。"""
    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name or username,
        is_admin=is_admin,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise
    await session.refresh(user)
    return user


async def ensure_default_admin(
    session: AsyncSession,
    username: str,
    password: str,
) -> User:
    """确保默认管理员账号存在，不覆盖已有管理员密码。"""
    user = await get_user_by_username(session, username)
    if user is not None:
        return user
    return await create_user(
        session,
        username=username,
        password=password,
        display_name=username,
        is_admin=True,
    )


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    """按用户名查询本地用户。"""
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def authenticate_user(session: AsyncSession, username: str, password: str) -> User | None:
    """校验用户名、账号状态和密码，成功时返回用户。"""
    user = await get_user_by_username(session, username)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def change_user_password(
    session: AsyncSession,
    user: User,
    old_password: str,
    new_password: str,
) -> bool:
    """校验旧密码后更新当前用户密码。"""
    if not verify_password(old_password, user.password_hash):
        return False
    user.password_hash = hash_password(new_password)
    await session.commit()
    await session.refresh(user)
    return True


async def create_user_session(
    session: AsyncSession,
    user_id: int,
    raw_token: str,
    days: int,
) -> UserSession:
    """创建服务端会话记录，只保存令牌哈希和过期时间。"""
    user_session = UserSession(
        user_id=user_id,
        token_hash=hash_session_token(raw_token),
        expires_at=session_expiry(days),
    )
    session.add(user_session)
    await session.commit()
    await session.refresh(user_session)
    return user_session


async def get_user_by_session_token(session: AsyncSession, raw_token: str) -> User | None:
    """根据原始会话令牌查找仍有效的登录用户。"""
    result = await session.execute(
        select(UserSession)
        .options(selectinload(UserSession.user))
        .where(UserSession.token_hash == hash_session_token(raw_token)),
    )
    stored_session = result.scalar_one_or_none()
    if stored_session is None or stored_session.revoked_at is not None:
        return None

    now = datetime.now(UTC)
    expires_at = stored_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        return None
    if not stored_session.user.is_active:
        return None

    stored_session.last_seen_at = now
    await session.commit()
    return stored_session.user


async def revoke_session_token(session: AsyncSession, raw_token: str) -> None:
    """撤销指定会话令牌，后续请求需要重新登录。"""
    result = await session.execute(
        select(UserSession).where(UserSession.token_hash == hash_session_token(raw_token)),
    )
    stored_session = result.scalar_one_or_none()
    if stored_session is None:
        return
    stored_session.revoked_at = datetime.now(UTC)
    await session.commit()
