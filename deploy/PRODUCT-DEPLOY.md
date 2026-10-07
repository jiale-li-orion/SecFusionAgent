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

## Boot

```bash
cp deploy/.env.production.example deploy/.env.production
# fill runtime secrets
mkdir -p deploy/secrets
docker run --rm httpd:2.4-alpine htpasswd -nbB secfusion 'choose-a-demo-password' \
  > deploy/secrets/product.htpasswd
# add SECFUSION_DEMO_HTPASSWD_PATH=./secrets/product.htpasswd to deploy/.env.production
docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml up -d --build
```

The product web image builds Vite with `/` as its base path. Nginx disables buffering for `/api/*`, so Investigation SSE can remain streaming through the reverse proxy.

## Public boundary

Production `product-web` is fail-closed behind Nginx Basic Auth. Compose refuses to start the web container until `SECFUSION_DEMO_HTPASSWD_PATH` resolves to an htpasswd file. `/healthz` is the only unauthenticated web route so container health checks keep working; `/`, `/api/*` and proxied `/health/*` stay behind the outer gate.

`X-Principal` remains an application principal coordinate, not authentication. Basic Auth is an explicit competition/demo access boundary, not an identity system. When a hostname is available, terminate TLS in front of `product-web` (or extend this Nginx layer with the selected certificate workflow) before exposing credentials over the network.

Stable competition demo entry points:

- `/product/demo` — resolves the current live guided path from real Product reads.
- `/product/demo/frozen` — enters the formal frozen BenchmarkRun / CaseRun proof path.

These routes only navigate existing facts. They do not seed demo telemetry, fabricate Cases, or rewrite benchmark results.

The product Nginx emits browser hardening headers (CSP, frame denial, no-sniff, no-referrer, and a restrictive Permissions-Policy). HSTS belongs to the TLS terminator because this container intentionally speaks plain HTTP behind that boundary; configure `Strict-Transport-Security` on the public HTTPS listener after the hostname and certificate are fixed.
