from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.application.authentication import (
    SESSION_COOKIE_NAME,
    AccountSessionModel,
    AccountUserModel,
    session_token_hash,
)
from apps.runtime_models import register_runtime_models
from packages.shared.db import Base

AUTH_HEADERS = {"X-SecFusion-CSRF": "1", "Origin": "http://test"}
REGISTRATION = {
    "email": "alice@example.invalid",
    "password": "correct-fixture-password",
    "display_name": "Alice",
}


@pytest.fixture
async def authentication_client() -> AsyncIterator[
    tuple[AsyncClient, async_sessionmaker[AsyncSession]]
]:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_account_registration_login_rotation_and_logout_are_durable(authentication_client):
    client, factory = authentication_client
    path = "/api/v1/auth"
    registered = await client.post(f"{path}/register", headers=AUTH_HEADERS, json=REGISTRATION)
    assert registered.status_code == 201, registered.text
    user = registered.json()["user"]
    assert set(user) == {"id", "email", "display_name"}
    assert registered.json()["authenticated"] is True
    assert "HttpOnly" in registered.headers["set-cookie"]
    assert "SameSite=lax" in registered.headers["set-cookie"]
    assert registered.headers["cache-control"] == "no-store"
    original_token = client.cookies.get(SESSION_COOKIE_NAME)
    async with factory() as session:
        stored_user = await session.get(AccountUserModel, user["id"])
        assert stored_user.password_hash.startswith("scrypt$131072$8$1$")
        assert REGISTRATION["password"] not in stored_user.password_hash
        stored_session = await session.get(AccountSessionModel, session_token_hash(original_token))
        assert stored_session is not None
        assert original_token not in stored_session.token_hash
    current = await client.get(f"{path}/me", headers={"X-Principal": "user:someone-else"})
    assert current.json()["user"] == user
    duplicate = await client.post(
        f"{path}/register",
        headers=AUTH_HEADERS,
        json={**REGISTRATION, "email": "ALICE@example.invalid"},
    )
    assert duplicate.status_code == 409
    wrong = await client.post(
        f"{path}/login",
        headers=AUTH_HEADERS,
        json={"email": REGISTRATION["email"], "password": "wrong-password"},
    )
    assert wrong.status_code == 401
    logged_in = await client.post(
        f"{path}/login",
        headers=AUTH_HEADERS,
        json={"email": REGISTRATION["email"], "password": REGISTRATION["password"]},
    )
    assert logged_in.status_code == 200
    rotated_token = client.cookies.get(SESSION_COOKIE_NAME)
    assert original_token != rotated_token
    old = await client.get(
        f"{path}/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={original_token}"}
    )
    assert old.json() == {"authenticated": False, "user": None}
    logout = await client.post(f"{path}/logout", headers=AUTH_HEADERS)
    assert logout.status_code == 200
    assert logout.json() == {"authenticated": False, "user": None}
    assert client.cookies.get(SESSION_COOKIE_NAME) is None
    replay = await client.get(
        f"{path}/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={rotated_token}"}
    )
    assert replay.json()["authenticated"] is False
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(AccountUserModel)) == 1
        sessions = list(await session.scalars(select(AccountSessionModel)))
        assert len(sessions) == 2
        assert all(row.revoked_at is not None for row in sessions)


@pytest.mark.asyncio
async def test_authentication_rejects_csrf_and_does_not_echo_passwords(authentication_client):
    client, factory = authentication_client
    assert (await client.get("/api/v1/auth/me", headers={"X-Principal": "user:forged"})).json() == {
        "authenticated": False,
        "user": None,
    }
    for headers in (
        {},
        {**AUTH_HEADERS, "Origin": "https://evil.invalid"},
        {**AUTH_HEADERS, "Origin": "null"},
        {**AUTH_HEADERS, "Origin": "http://[invalid"},
        {**AUTH_HEADERS, "Sec-Fetch-Site": "cross-site"},
    ):
        denied = await client.post("/api/v1/auth/register", headers=headers, json=REGISTRATION)
        assert denied.status_code == 403
    short_password = "secret-xx"
    invalid = await client.post(
        "/api/v1/auth/register",
        headers=AUTH_HEADERS,
        json={**REGISTRATION, "password": short_password},
    )
    assert invalid.status_code == 422
    assert short_password not in invalid.text
    unknown = await client.post(
        "/api/v1/auth/login",
        headers=AUTH_HEADERS,
        json={"email": "nobody@example.invalid", "password": "wrong-password"},
    )
    assert unknown.status_code == 401
    assert unknown.json()["code"] == "invalid_credentials"
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(AccountUserModel)) == 0
        assert await session.scalar(select(func.count()).select_from(AccountSessionModel)) == 0


@pytest.mark.asyncio
async def test_expired_or_forged_session_cannot_authenticate(authentication_client):
    client, factory = authentication_client
    registered = await client.post("/api/v1/auth/register", headers=AUTH_HEADERS, json=REGISTRATION)
    assert registered.status_code == 201
    token = client.cookies.get(SESSION_COOKIE_NAME)
    async with factory() as session, session.begin():
        await session.execute(
            update(AccountSessionModel).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
    expired = await client.get("/api/v1/auth/me")
    assert expired.json()["authenticated"] is False
    forged = await client.get(
        "/api/v1/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={'x' * 43}"}
    )
    assert forged.json()["authenticated"] is False
    assert token not in forged.text


@pytest.mark.asyncio
async def test_production_session_cookie_is_secure(authentication_client, monkeypatch):
    import apps.api.routes.authentication as route
    from packages.shared.config import Settings

    client, _factory = authentication_client
    settings = Settings(environment="production")
    monkeypatch.setattr(route, "get_settings", lambda: settings)
    registered = await client.post("/api/v1/auth/register", headers=AUTH_HEADERS, json=REGISTRATION)
    assert registered.status_code == 201
    assert "Secure" in registered.headers["set-cookie"]


@pytest.mark.asyncio
async def test_account_conversations_and_preferences_are_cookie_owned(authentication_client):
    from apps.application.question_sessions import QuestionSessionStore

    client, factory = authentication_client
    path = "/api/v1/questions/sessions"
    assert (await client.get(path, headers={"X-Principal": "user:alice"})).status_code == 401
    alice = await client.post("/api/v1/auth/register", headers=AUTH_HEADERS, json=REGISTRATION)
    alice_id = alice.json()["user"]["id"]
    alice_token = client.cookies.get(SESSION_COOKIE_NAME)
    async with factory() as session, session.begin():
        for index in range(2):
            await QuestionSessionStore().append_turn(
                session, session_id="alice-conversation", principal=f"user:{alice_id}",
                request_id=f"alice-question-{index}", question=f"Alice private question {index}",
                task_kind="lookup", target_object_ids=[], knowledge_revision=None,
                context_id=None, decision_ref=f"decision-{index}", investigation_ref=None,
            )
    preferences = "/api/v1/intelligence/preferences"
    saved = await client.put(preferences, headers=AUTH_HEADERS, json={"keywords": ["vLLM"]})
    assert saved.status_code == 200, saved.text
    assert (await client.put(preferences, json={"keywords": []})).status_code == 403
    page = await client.get(path)
    assert page.status_code == 200, page.text
    assert len(page.json()["items"]) == 1
    assert page.json()["items"][0]["latest_turn"]["question"] == "Alice private question 1"
    bob = await client.post(
        "/api/v1/auth/register", headers=AUTH_HEADERS,
        json={**REGISTRATION, "email": "bob@example.invalid", "display_name": "Bob"},
    )
    assert bob.status_code == 201
    forged = {"X-Principal": f"user:{alice_id}"}
    assert (await client.get(path, headers=forged)).json()["items"] == []
    assert (await client.get(preferences, headers=forged)).json()["keywords"] == []
    assert (await client.get(f"{path}/alice-conversation", headers=forged)).status_code == 403
    revoked = {"Cookie": f"{SESSION_COOKIE_NAME}={alice_token}"}
    assert (await client.get(path, headers=revoked)).status_code == 401
    restored = await client.post(
        "/api/v1/auth/login", headers=AUTH_HEADERS,
        json={"email": REGISTRATION["email"], "password": REGISTRATION["password"]},
    )
    assert restored.status_code == 200
    assert (await client.get(path)).json()["items"][0]["session_id"] == "alice-conversation"
    assert (await client.get(preferences)).json()["keywords"] == ["vLLM"]


@pytest.mark.asyncio
async def test_account_conversation_and_turn_pages_keep_owner_boundary(authentication_client):
    from apps.application.question_sessions import QuestionSessionStore

    def fixed_clock(at: datetime) -> Callable[[], datetime]:
        return lambda: at

    client, factory = authentication_client
    registered = await client.post("/api/v1/auth/register", headers=AUTH_HEADERS, json=REGISTRATION)
    assert registered.status_code == 201
    principal = f"user:{registered.json()['user']['id']}"
    async with factory() as session, session.begin():
        for index in range(3):
            timestamp = datetime(2026, 10, 9, tzinfo=UTC) + timedelta(minutes=index)
            store = QuestionSessionStore(now=fixed_clock(timestamp))
            for turn in range(5 if index == 2 else 1):
                await store.append_turn(
                    session, session_id=f"paged-session-{index}", principal=principal,
                    request_id=f"paged-request-{index}-{turn}", question=f"Question {index}/{turn}",
                    task_kind="lookup", target_object_ids=[], knowledge_revision=None,
                    context_id=None, decision_ref=f"decision-{index}-{turn}",
                    investigation_ref=None,
                )

    path = "/api/v1/questions/sessions"
    first = await client.get(path, params={"limit": 2})
    assert [item["session_id"] for item in first.json()["items"]] == [
        "paged-session-2", "paged-session-1"
    ]
    assert first.json()["has_more"] is True
    second = await client.get(path, params={"limit": 2, "cursor": first.json()["next_cursor"]})
    assert [item["session_id"] for item in second.json()["items"]] == ["paged-session-0"]
    assert second.json()["has_more"] is False

    history_path = f"{path}/paged-session-2"
    latest = await client.get(history_path, params={"limit": 2})
    assert [turn["turn_index"] for turn in latest.json()["turns"]] == [4, 5]
    middle = await client.get(history_path, params={"limit": 2, "before_turn": 4})
    assert [turn["turn_index"] for turn in middle.json()["turns"]] == [2, 3]
    oldest = await client.get(history_path, params={"limit": 2, "before_turn": 2})
    assert [turn["turn_index"] for turn in oldest.json()["turns"]] == [1]
    assert oldest.json()["has_more"] is False

    bob = await client.post(
        "/api/v1/auth/register", headers=AUTH_HEADERS,
        json={**REGISTRATION, "email": "bob-paging@example.invalid"},
    )
    assert bob.status_code == 201
    assert (await client.get(path, params={"cursor": "paged-session-1"})).status_code == 403
    assert (await client.get(history_path, params={"before_turn": 4})).status_code == 403
