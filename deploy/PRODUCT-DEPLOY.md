# SecFusionAgent Product Deployment

Production is a single browser entry: `product-web`. PostgreSQL and Redis remain private on the Compose network.

```text
Internet / TLS layer
        ↓
product-web :80
  ├─ /          React Product App
  ├─ /api/*     FastAPI
  └─ /health*   FastAPI / web health
        ↓
api → PostgreSQL / Redis roles / ArtifactStore
        ↓
workers / scheduler / task-event runtime
```

The retired Runtime Workbench is not deployed.

## Local Docker DNS

If a development worker reports `Temporary failure in name resolution`, inspect its
`/etc/resolv.conf`. Docker's internal `127.0.0.11` resolver needs a reachable upstream
resolver; an internal resolver with no external nameservers cannot call model or
collection providers. Set `SECFUSION_DNS_SERVER` to a resolver reachable from the
containers (on WSL, inspect the host's `/etc/resolv.conf`) and apply the optional
development override from a shell with the local model environment loaded:

```bash
. ./activate.sh
export SECFUSION_DNS_SERVER=your-reachable-resolver
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dns.yml \
  --profile runtime up -d worker worker-collection scheduler \
  task-event-dispatcher task-event-scheduler
```

Verify resolution inside `worker` and submit a fresh VERIFY question. Failed Cases
remain recorded as failed; restoring connectivity does not rewrite their history.
The override is opt-in and does not change the default or production DNS settings.

When host networking works only through a local HTTP proxy, set
`SECFUSION_UPSTREAM_HTTP_PROXY` for the containers. For a proxy listening on the
host's loopback address, the optional development relay can expose it on the Docker
bridge without binding a public interface:

```bash
.venv/bin/python scripts/local_proxy_bridge.py --bind 172.17.0.1 --port 17897 --upstream-port 7897
export SECFUSION_UPSTREAM_HTTP_PROXY=http://172.17.0.1:17897
docker compose -f deploy/docker-compose.yml --profile runtime up -d worker worker-collection scheduler task-event-dispatcher task-event-scheduler
```

Keep the relay process running while workers need external providers. Override
`SECFUSION_NO_PROXY` if the deployment has additional private services or a model
endpoint that must bypass the proxy. Scheduled collection explicitly proxies only
`SECFUSION_SOURCE_PROXY_IDS` (the CVE Raw feed, MITRE ATLAS and Meta AI by default);
other scheduled sources connect directly even when the general worker proxy is set.
Set `SECFUSION_SOURCE_PROXY_IDS='["*"]'` only where every scheduled source requires
the proxy. A proxy may restore reachability without
overriding upstream 403 or rate-limit responses; source health still reports those
conditions.

## Boot

```bash
cp deploy/.env.production.example deploy/.env.production
# fill runtime secrets
docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml up -d --build
```

The product web image builds Vite with `/` as its base path. Nginx disables buffering for `/api/*`, so question-token and Investigation SSE remain streaming through the reverse proxy.

## Public boundary

Production `product-web` serves the public Product entry and account sign-in. Private Questions, sessions, Cases, Decisions and Task audit APIs require a server-owned account session; public WORLD and shared Evidence/Knowledge reads remain available. `/healthz` is available for container health checks. Configure `SECFUSION_AUTH_ALLOWED_ORIGINS` to the exact external browser origin, and terminate TLS in front of `product-web` before public access so production Secure session cookies work.

`X-Principal` remains an application principal coordinate, not authentication. The API resolves identity from an HttpOnly, Secure account-session cookie and checks Origin/CSRF on writes. A TLS terminator must pass the original scheme to Nginx and onward to FastAPI.

The browser entry serves the live product. Evaluation and competition records remain backend engineering capabilities; demo and frozen-proof navigation are not exposed in the application.

The product Nginx emits browser hardening headers (CSP, frame denial, no-sniff, no-referrer, and a restrictive Permissions-Policy). HSTS belongs to the TLS terminator because this container intentionally speaks plain HTTP behind that boundary; configure `Strict-Transport-Security` on the public HTTPS listener after the hostname and certificate are fixed.
