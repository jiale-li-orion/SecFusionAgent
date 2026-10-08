from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from apps.api.authentication import verify_authentication_origin
from apps.api.dependencies import SessionDep
from apps.application.authentication import (
    SESSION_COOKIE_NAME,
    issue_account_session,
    login_account,
    register_account,
    resolve_authenticated_account,
    revoke_account_session,
)
from apps.application.views.authentication import (
    AccountSessionView,
    LoginAccountInput,
    RegisterAccountInput,
)
from packages.shared.config import get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _cookie_secure(request: Request) -> bool:
    return request.url.scheme == "https" or get_settings().environment not in {"dev", "test"}


def _private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _set_session_cookie(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=get_settings().auth_session_ttl_seconds,
        httponly=True,
        secure=_cookie_secure(request),
        samesite="lax",
        path="/",
    )
    _private_response(response)


@router.post(
    "/register",
    status_code=201,
    response_model=AccountSessionView,
    dependencies=[Depends(verify_authentication_origin)],
)
async def account_register(
    body: RegisterAccountInput,
    request: Request,
    response: Response,
    session: SessionDep,
) -> AccountSessionView:
    user = await register_account(session, body)
    await revoke_account_session(session, request.cookies.get(SESSION_COOKIE_NAME))
    token = await issue_account_session(session, user.id)
    await session.commit()
    _set_session_cookie(request, response, token)
    return AccountSessionView(authenticated=True, user=user)


@router.post(
    "/login",
    response_model=AccountSessionView,
    dependencies=[Depends(verify_authentication_origin)],
)
async def account_login(
    body: LoginAccountInput,
    request: Request,
    response: Response,
    session: SessionDep,
) -> AccountSessionView:
    user = await login_account(session, body)
    # Rotate any previous cookie; never accept caller-supplied session identities.
    await revoke_account_session(session, request.cookies.get(SESSION_COOKIE_NAME))
    token = await issue_account_session(session, user.id)
    await session.commit()
    _set_session_cookie(request, response, token)
    return AccountSessionView(authenticated=True, user=user)


@router.get("/me", response_model=AccountSessionView)
async def account_me(
    request: Request, response: Response, session: SessionDep
) -> AccountSessionView:
    account = await resolve_authenticated_account(request, session)
    _private_response(response)
    return AccountSessionView(
        authenticated=account is not None, user=account.user if account else None
    )


@router.post(
    "/logout",
    response_model=AccountSessionView,
    dependencies=[Depends(verify_authentication_origin)],
)
async def account_logout(
    request: Request, response: Response, session: SessionDep
) -> AccountSessionView:
    await revoke_account_session(session, request.cookies.get(SESSION_COOKIE_NAME))
    await session.commit()
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=_cookie_secure(request),
        samesite="lax",
    )
    _private_response(response)
    return AccountSessionView(authenticated=False)
