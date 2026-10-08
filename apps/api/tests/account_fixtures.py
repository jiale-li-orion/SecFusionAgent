"""Persisted opaque account sessions for Product HTTP tests."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.application.authentication import (
    SESSION_COOKIE_NAME,
    AccountSessionModel,
    AccountUserModel,
    session_token_hash,
)


def account_headers(user_id: str = "test") -> dict[str, str]:
    token = f"test-account-{user_id}".ljust(43, "_")
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}", "X-SecFusion-CSRF": "1"}


async def seed_test_accounts(factory: async_sessionmaker[AsyncSession]) -> None:
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        for user_id in ("test", "other", "owner", "local"):
            session.add(
                AccountUserModel(
                    user_id=user_id,
                    email=f"{user_id}@example.invalid",
                    display_name=user_id,
                    password_hash="fixture-not-login-capable",
                    active=True,
                    created_at=now,
                )
            )
        await session.flush()
        for user_id in ("test", "other", "owner", "local"):
            token = f"test-account-{user_id}".ljust(43, "_")
            session.add(
                AccountSessionModel(
                    token_hash=session_token_hash(token),
                    user_id=user_id,
                    created_at=now,
                    expires_at=datetime(2099, 1, 1, tzinfo=UTC),
                )
            )
