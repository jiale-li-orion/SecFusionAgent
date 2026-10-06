from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NGINX = ROOT / "deploy/product-web/nginx.conf"
SECURITY_HEADERS = ROOT / "deploy/product-web/security-headers.conf"
COMPOSE = ROOT / "deploy/docker-compose.production.yml"
DOC = ROOT / "deploy/PRODUCT-DEPLOY.md"


def _require(text: str, needle: str, *, owner: str) -> None:
    if needle not in text:
        raise RuntimeError(f"{owner} missing required product boundary: {needle}")


def _location_block(nginx: str, location: str) -> str:
    match = re.search(
        rf"location\s+{re.escape(location)}\s*\{{(?P<body>.*?)\n\s*\}}",
        nginx,
        re.DOTALL,
    )
    if match is None:
        raise RuntimeError(f"nginx missing location {location}")
    return match.group("body")


def main() -> int:
    nginx = NGINX.read_text(encoding="utf-8")
    security_headers = SECURITY_HEADERS.read_text(encoding="utf-8")
    compose = COMPOSE.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")

    _require(nginx, 'auth_basic "SecFusion competition demo";', owner="nginx")
    _require(
        nginx,
        "auth_basic_user_file /etc/nginx/auth/.htpasswd;",
        owner="nginx",
    )
    _require(nginx, "server_tokens off;", owner="nginx")
    _require(
        nginx,
        "include /etc/nginx/snippets/security-headers.conf;",
        owner="nginx",
    )
    for header in (
        'X-Content-Type-Options "nosniff"',
        'X-Frame-Options "DENY"',
        'Referrer-Policy "no-referrer"',
        'Permissions-Policy "camera=(), microphone=(), geolocation=()"',
        "Content-Security-Policy",
    ):
        _require(security_headers, header, owner="nginx security headers")
    healthz = _location_block(nginx, "= /healthz")
    _require(healthz, "auth_basic off;", owner="nginx /healthz")
    _require(
        healthz,
        "include /etc/nginx/snippets/security-headers.conf;",
        owner="nginx /healthz",
    )

    api = _location_block(nginx, "/api/")
    _require(api, "proxy_pass http://api:8000;", owner="nginx /api")
    _require(api, "proxy_buffering off;", owner="nginx /api")
    _require(api, "proxy_cache off;", owner="nginx /api")
    _require(api, "proxy_read_timeout 3600s;", owner="nginx /api")
    _require(
        api,
        "proxy_set_header X-Forwarded-Proto $scheme;",
        owner="nginx /api",
    )

    health = _location_block(nginx, "/health")
    if "auth_basic off;" in health:
        raise RuntimeError("proxied /health must remain behind demo authentication")

    assets = _location_block(nginx, "/assets/")
    _require(
        assets,
        "include /etc/nginx/snippets/security-headers.conf;",
        owner="nginx /assets",
    )
    _require(assets, 'Cache-Control "public, immutable"', owner="nginx /assets")
    root = _location_block(nginx, "/")
    _require(
        root,
        "include /etc/nginx/snippets/security-headers.conf;",
        owner="nginx /",
    )

    _require(
        compose,
        "${SECFUSION_DEMO_HTPASSWD_PATH:?set SECFUSION_DEMO_HTPASSWD_PATH",
        owner="production compose",
    )
    _require(compose, "${SECFUSION_HTTP_PORT:-80}:80", owner="production compose")

    for service in ("postgres", "redis-broker", "redis-cache", "redis-task-bus", "api"):
        service_match = re.search(
            rf"^\s{{2}}{re.escape(service)}:\n(?P<body>.*?)(?=^\s{{2}}\S|\Z)",
            compose,
            re.MULTILINE | re.DOTALL,
        )
        if service_match is None:
            raise RuntimeError(f"production compose missing service {service}")
        if re.search(r"^\s+ports:\s*$", service_match.group("body"), re.MULTILINE):
            raise RuntimeError(f"{service} must not publish host ports in production")

    _require(
        doc,
        "terminate TLS in front of `product-web`",
        owner="deployment documentation",
    )
    _require(
        doc,
        "HSTS belongs to the TLS terminator",
        owner="deployment documentation",
    )
    _require(
        doc,
        "`X-Principal` remains an application principal coordinate, not authentication",
        owner="deployment documentation",
    )

    print("PRODUCT DEPLOY GATE PASS")
    print("PASS · fail-closed Basic Auth")
    print("PASS · /healthz is the sole unauthenticated health route")
    print("PASS · SSE proxy buffering/cache disabled")
    print("PASS · PostgreSQL/Redis/API have no host port exposure")
    print("PASS · immutable hashed assets")
    print("PASS · browser hardening headers")
    print("PASS · forwarded TLS protocol seam documented and proxied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
