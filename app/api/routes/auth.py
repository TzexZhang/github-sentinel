from fastapi import APIRouter, Response

from app.api.deps import DbSession, CurrentUser
from app.core.config import settings
from app.core.errors import ApiError
from sqlalchemy.exc import IntegrityError

from app.repositories.users import (
    authenticate_user,
    change_user_password,
    create_user_session,
    create_user,
    ensure_default_admin,
    revoke_session_token,
)
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, UserRead
from app.schemas.responses import ApiResponse, success_response
from app.services.auth import generate_session_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=ApiResponse, status_code=201)
async def register_endpoint(
    payload: RegisterRequest,
    session: DbSession,
) -> dict[str, object]:
    """注册新的本地普通用户。"""
    try:
        user = await create_user(
            session,
            username=payload.username,
            password=payload.password,
            display_name=payload.username,
            is_admin=False,
        )
    except IntegrityError as exc:
        raise ApiError(
            status_code=409,
            code="username_conflict",
            message="用户名已存在。",
        ) from exc
    return success_response(UserRead.model_validate(user).model_dump(), code=201)


@router.post("/login", response_model=ApiResponse)
async def login_endpoint(
    payload: LoginRequest,
    session: DbSession,
    response: Response,
) -> dict[str, object]:
    """校验账号密码并写入 7 天内免登录的 Cookie 会话。"""
    await ensure_default_admin(session, settings.admin_username, settings.admin_password)
    user = await authenticate_user(session, payload.username, payload.password)
    if user is None:
        raise ApiError(
            status_code=401,
            code="invalid_credentials",
            message="用户名或密码错误。",
        )

    token = generate_session_token()
    await create_user_session(session, user.id, token, settings.auth_session_days)
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
    )
    return success_response(UserRead.model_validate(user).model_dump())


@router.post("/logout", response_model=ApiResponse)
async def logout_endpoint(
    session: DbSession,
    current_user: CurrentUser,
    response: Response,
) -> dict[str, object]:
    """撤销当前会话并清理登录 Cookie。"""
    if current_user.session_token:
        await revoke_session_token(session, current_user.session_token)
    response.delete_cookie(settings.auth_cookie_name)
    return success_response(None)


@router.post("/change-password", response_model=ApiResponse)
async def change_password_endpoint(
    payload: ChangePasswordRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> dict[str, object]:
    """校验当前密码后修改登录用户的密码。"""
    changed = await change_user_password(
        session,
        current_user.user,
        payload.old_password,
        payload.new_password,
    )
    if not changed:
        raise ApiError(
            status_code=401,
            code="invalid_current_password",
            message="当前密码错误。",
        )
    return success_response(None)


@router.get("/me", response_model=ApiResponse)
async def me_endpoint(current_user: CurrentUser) -> dict[str, object]:
    """返回当前登录用户信息。"""
    return success_response(UserRead.model_validate(current_user.user).model_dump())
