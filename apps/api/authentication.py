"""Same-origin mutation guard shared by auth and authenticated Product routes."""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import Request

from apps.application.errors import ApplicationError
from packages.shared.config import get_settings


class AuthenticationCsrfError(ApplicationError):
    code = "csrf_rejected"


def _origin(value: str) -> str | None:
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.path not in {"", "/"}:
        return None
    if parts.username or parts.password or parts.query or parts.fragment:
        return None
    return f"{parts.scheme.casefold()}://{parts.netloc.casefold()}".rstrip("/")


def verify_authentication_origin(request: Request) -> None:
    """Explicit mutation intent plus same-origin checks, including login CSRF."""
    if request.headers.get("X-SecFusion-CSRF") != "1":
        raise AuthenticationCsrfError("same-origin authentication request required")
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        raise AuthenticationCsrfError("cross-site authentication request rejected")
    supplied = request.headers.get("Origin")
    if supplied is not None:
        current = f"{request.url.scheme}://{request.url.netloc}".casefold()
        allowed = {
            current,
            *(
                normalized
                for value in get_settings().auth_allowed_origins
                if (normalized := _origin(value)) is not None
            ),
        }
        if _origin(supplied) not in allowed:
            raise AuthenticationCsrfError("authentication origin rejected")
