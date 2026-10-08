"""Database account and opaque-session authority for Product principals."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import Request
from sqlalchemy import Boolean, DateTime, ForeignKey, String, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from apps.application.errors import ApplicationError
from apps.application.views.authentication import (
    AccountUserView,
    LoginAccountInput,
    RegisterAccountInput,
)
from packages.shared.config import get_settings
from packages.shared.db import Base

SESSION_COOKIE_NAME = "secfusion_session"
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**17, 8, 1
SCRYPT_MAX_MEMORY = 256 * 1024 * 1024
_password_slots = asyncio.Semaphore(2)


class InvalidCredentialsError(ApplicationError):
    code = "invalid_credentials"


class AccountExistsError(ApplicationError):
    code = "account_exists"


class AuthenticationBusyError(ApplicationError):
    code = "rate_limited"


class AccountUserModel(Base):
    __tablename__ = "account_users"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AccountSessionModel(Base):
    __tablename__ = "account_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("account_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


@dataclass(frozen=True)
class AuthenticatedAccount:
    user: AccountUserView

    @property
    def principal(self) -> str:
        return f"user:{self.user.id}"


def _user_view(user: AccountUserModel) -> AccountUserView:
    return AccountUserView(id=user.user_id, email=user.email, display_name=user.display_name)


def session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _scrypt(password: str, salt: bytes) -> str:
    # OWASP's minimum scrypt profile: N=2^17, r=8, p=1 (128 MiB).
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=SCRYPT_MAX_MEMORY,
        dklen=32,
    ).hex()


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${_scrypt(password, salt)}"


def _verify_password(password: str, encoded: str | None) -> bool:
    # Missing users still pay the same KDF cost. Stored parameters are versioned,
    # never accepted as arbitrary memory/CPU configuration from a database string.
    salt, expected = bytes(16), "0" * 64
    valid = False
    if encoded is not None:
        parts = encoded.split("$")
        if len(parts) == 6 and parts[:4] == ["scrypt", str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P)]:
            try:
                candidate_salt = bytes.fromhex(parts[4])
                if len(candidate_salt) == 16 and re.fullmatch(r"[0-9a-f]{64}", parts[5]):
                    salt, expected, valid = candidate_salt, parts[5], True
            except ValueError:
                pass
    matched = hmac.compare_digest(_scrypt(password, salt), expected)
    return valid and matched


async def _password_work[**P, T](
    function: Callable[P, T], *arguments: P.args, **kwargs: P.kwargs
) -> T:
    try:
        await asyncio.wait_for(_password_slots.acquire(), timeout=1)
    except TimeoutError as exc:
        raise AuthenticationBusyError("authentication temporarily busy") from exc
    work = asyncio.create_task(asyncio.to_thread(function, *arguments, **kwargs))
    release_deferred = False
    try:
        return await asyncio.shield(work)
    except asyncio.CancelledError:
        # A disconnected caller must not free a memory slot while its KDF thread
        # is still running. Return the slot only when that real work finishes.
        release_deferred = True

        def release_when_finished(task: asyncio.Task[T]) -> None:
            if not task.cancelled():
                task.exception()
            _password_slots.release()

        work.add_done_callback(release_when_finished)
        raise
    finally:
        if not release_deferred:
            _password_slots.release()


async def register_account(session: AsyncSession, body: RegisterAccountInput) -> AccountUserView:
    encoded = await _password_work(_hash_password, body.password.get_secret_value())
    user = AccountUserModel(
        user_id=str(uuid4()),
        email=body.email,
        display_name=body.display_name,
        password_hash=encoded,
        active=True,
        created_at=datetime.now(UTC),
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AccountExistsError("an account with this email already exists") from exc
    return _user_view(user)


async def login_account(session: AsyncSession, body: LoginAccountInput) -> AccountUserView:
    user = await session.scalar(
        select(AccountUserModel).where(AccountUserModel.email == body.email)
    )
    valid = await _password_work(
        _verify_password,
        body.password.get_secret_value(),
        user.password_hash if user else None,
    )
    if not valid or user is None or not user.active:
        raise InvalidCredentialsError("email or password is incorrect")
    return _user_view(user)


async def issue_account_session(session: AsyncSession, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    session.add(
        AccountSessionModel(
            token_hash=session_token_hash(token),
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(seconds=get_settings().auth_session_ttl_seconds),
        )
    )
    await session.flush()
    return token


async def revoke_account_session(session: AsyncSession, token: str | None) -> None:
    if token is not None and re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        await session.execute(
            update(AccountSessionModel)
            .where(
                AccountSessionModel.token_hash == session_token_hash(token),
                AccountSessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )


async def resolve_authenticated_account(
    request: Request,
    session: AsyncSession,
) -> AuthenticatedAccount | None:
    """Resolve the server-owned cookie only; caller-provided principals have no authority."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None or re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None:
        return None
    user = await session.scalar(
        select(AccountUserModel)
        .join(
            AccountSessionModel,
            AccountSessionModel.user_id == AccountUserModel.user_id,
        )
        .where(
            AccountSessionModel.token_hash == session_token_hash(token),
            AccountSessionModel.expires_at > datetime.now(UTC),
            AccountSessionModel.revoked_at.is_(None),
            AccountUserModel.active.is_(True),
        )
    )
    return AuthenticatedAccount(_user_view(user)) if user is not None else None
