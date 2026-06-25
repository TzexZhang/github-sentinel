from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import User, UserSession
from app.repositories.users import create_user
from app.services.auth import verify_password


async def test_login_sets_http_only_session_cookie_for_seven_days(anonymous_client):
    response = await anonymous_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["username"] == "admin"
    cookie = response.headers["set-cookie"]
    assert "github_sentinel_session=" in cookie
    assert "HttpOnly" in cookie
    assert "Max-Age=604800" in cookie
    assert "SameSite=lax" in cookie


async def test_protected_subscription_endpoint_rejects_missing_session(anonymous_client):
    response = await anonymous_client.get("/api/subscriptions")

    assert response.status_code == 401
    assert response.json()["data"]["error_code"] == "authentication_required"


async def test_me_returns_current_user_after_cookie_login(anonymous_client):
    login_response = await anonymous_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )

    assert login_response.status_code == 200
    response = await anonymous_client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["data"]["username"] == "admin"


async def test_logout_revokes_session_cookie(anonymous_client):
    await anonymous_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )

    logout_response = await anonymous_client.post("/api/auth/logout")
    me_response = await anonymous_client.get("/api/auth/me")

    assert logout_response.status_code == 200
    assert me_response.status_code == 401


async def test_change_password_updates_hash_and_allows_new_login(anonymous_client, session_factory):
    await anonymous_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )

    response = await anonymous_client.post(
        "/api/auth/change-password",
        json={"old_password": "123456", "new_password": "new123"},
    )
    old_login = await anonymous_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    new_login = await anonymous_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "new123"},
    )

    assert response.status_code == 200
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        stored = result.scalar_one()
    assert stored.password_hash != "new123"
    assert verify_password("new123", stored.password_hash)


async def test_change_password_rejects_wrong_current_password(anonymous_client):
    await anonymous_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )

    response = await anonymous_client.post(
        "/api/auth/change-password",
        json={"old_password": "wrong", "new_password": "new123"},
    )

    assert response.status_code == 401
    assert response.json()["data"]["error_code"] == "invalid_current_password"


async def test_change_password_validates_new_password_length(anonymous_client):
    await anonymous_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )

    response = await anonymous_client.post(
        "/api/auth/change-password",
        json={"old_password": "123456", "new_password": "short"},
    )

    assert response.status_code == 422


async def test_create_user_hashes_password(session_factory):
    async with session_factory() as session:
        user = await create_user(session, username="alice", password="correct horse")
        result = await session.execute(select(User).where(User.id == user.id))
        stored = result.scalar_one()

    assert stored.password_hash != "correct horse"
    assert verify_password("correct horse", stored.password_hash)
    assert not verify_password("wrong", stored.password_hash)


async def test_expired_session_is_rejected(anonymous_client, session_factory):
    async with session_factory() as session:
        user = await create_user(session, username="bob", password="secret")
        expired = UserSession(
            user_id=user.id,
            token_hash="expired-token",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        session.add(expired)
        await session.commit()

    anonymous_client.cookies.set("github_sentinel_session", "raw-token")
    response = await anonymous_client.get("/api/auth/me")

    assert response.status_code == 401


async def test_dashboard_requires_login_cookie(anonymous_client):
    response = await anonymous_client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_dashboard_is_accessible_after_login(client):
    response = await client.get("/dashboard", follow_redirects=False)

    assert response.status_code != 303


async def test_register_creates_user_with_hashed_password(anonymous_client, session_factory):
    response = await anonymous_client.post(
        "/api/auth/register",
        json={"username": "alice_01", "password": "secret1"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["username"] == "alice_01"
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.username == "alice_01"))
        stored = result.scalar_one()
    assert stored.password_hash != "secret1"
    assert verify_password("secret1", stored.password_hash)


async def test_register_validates_username_and_password_rules(anonymous_client):
    invalid_username = await anonymous_client.post(
        "/api/auth/register",
        json={"username": "a-b", "password": "secret1"},
    )
    short_password = await anonymous_client.post(
        "/api/auth/register",
        json={"username": "alice_02", "password": "short"},
    )

    assert invalid_username.status_code == 422
    assert short_password.status_code == 422


async def test_register_rejects_duplicate_username(anonymous_client):
    first = await anonymous_client.post(
        "/api/auth/register",
        json={"username": "alice_03", "password": "secret1"},
    )
    second = await anonymous_client.post(
        "/api/auth/register",
        json={"username": "alice_03", "password": "secret1"},
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["data"]["error_code"] == "username_conflict"


async def test_login_page_shows_login_and_register_mutually_exclusive(anonymous_client):
    response = await anonymous_client.get("/login")

    assert response.status_code == 200
    body = response.text
    assert "Git Sentinel" in body
    assert body.index('id="loginForm"') < body.index('id="registerForm"')
    assert '<form id="registerForm" hidden>' in body
    assert "[hidden] { display: none !important; }" in body
    assert 'id="showRegisterButton"' in body
    assert 'id="showLoginButton"' in body
    assert "showRegister()" in body
    assert "showLogin()" in body
    assert "GitHub Sentinel" not in body
