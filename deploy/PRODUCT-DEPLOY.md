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

## Boot

```bash
cp deploy/.env.production.example deploy/.env.production
# fill runtime secrets
mkdir -p deploy/secrets
docker run --rm httpd:2.4-alpine htpasswd -nbB secfusion 'choose-a-strong-password' \
  > deploy/secrets/product.htpasswd
# add SECFUSION_DEMO_HTPASSWD_PATH=./secrets/product.htpasswd to deploy/.env.production
docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml up -d --build
```

The product web image builds Vite with `/` as its base path. Nginx disables buffering for `/api/*`, so Investigation SSE can remain streaming through the reverse proxy.

## Public boundary

Production `product-web` is fail-closed behind Nginx Basic Auth. Compose refuses to start the web container until `SECFUSION_DEMO_HTPASSWD_PATH` resolves to an htpasswd file. `/healthz` is the only unauthenticated web route so container health checks keep working; `/`, `/api/*` and proxied `/health/*` stay behind the outer gate.

`X-Principal` remains an application principal coordinate, not authentication. Basic Auth is an explicit outer access boundary, not an identity system. When a hostname is available, terminate TLS in front of `product-web` (or extend this Nginx layer with the selected certificate workflow) before exposing credentials over the network.

The browser entry serves the live product. Evaluation and competition records remain backend engineering capabilities; demo and frozen-proof navigation are not exposed in the application.

The product Nginx emits browser hardening headers (CSP, frame denial, no-sniff, no-referrer, and a restrictive Permissions-Policy). HSTS belongs to the TLS terminator because this container intentionally speaks plain HTTP behind that boundary; configure `Strict-Transport-Security` on the public HTTPS listener after the hostname and certificate are fixed.
