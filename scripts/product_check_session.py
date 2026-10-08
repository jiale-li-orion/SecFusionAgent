"""In-memory session input for live Product checks; never persist credentials."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener, urlopen


def product_session_cookie() -> str | None:
    value = os.environ.get("SECFUSION_PRODUCT_SESSION_COOKIE", "").strip()
    if not value:
        return None
    token = value.removeprefix("secfusion_session=")
    if re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None:
        raise RuntimeError("SECFUSION_PRODUCT_SESSION_COOKIE must contain an opaque session token")
    return f"secfusion_session={token}"


def request_headers(accept: str, cookie: str | None = None) -> dict[str, str]:
    headers = {"Accept": accept}
    if cookie is not None:
        headers["Cookie"] = cookie
    return headers


def open_product_request(request: Request, *, timeout: float = 8) -> Any:
    # Loopback Product requests must stay local, including account cookies.
    # Preserve the caller's configured proxy policy for actual remote deployments.
    if urlsplit(request.full_url).hostname in {"127.0.0.1", "localhost", "::1"}:
        return build_opener(ProxyHandler({})).open(request, timeout=timeout)
    return urlopen(request, timeout=timeout)
