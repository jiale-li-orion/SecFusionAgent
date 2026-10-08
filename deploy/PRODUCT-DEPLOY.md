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
SECFUSION_HOST_PROXY_PORT=7899 # set this to the host proxy listener
.venv/bin/python scripts/local_proxy_bridge.py --bind 172.17.0.1 --port 17897 --upstream-port "$SECFUSION_HOST_PROXY_PORT"
export SECFUSION_UPSTREAM_HTTP_PROXY=http://172.17.0.1:17897
docker compose -f deploy/docker-compose.yml --profile runtime up -d worker worker-collection scheduler task-event-dispatcher task-event-scheduler
```

Keep the relay process running while selected sources need it. The proxy setting
does not become a process-wide `HTTP_PROXY`: model and task workers connect to
their providers directly. Scheduled collection explicitly proxies only
`SECFUSION_SOURCE_PROXY_IDS` (CVE Raw, MITRE ATLAS, Meta AI, GitHub repositories,
BleepingComputer and the SlowMist report download by default); other scheduled
sources connect directly.
Set `SECFUSION_SOURCE_PROXY_IDS='["*"]'` only where every scheduled source requires
the proxy. A proxy may restore reachability without
overriding upstream 403 or rate-limit responses; source health still reports those
conditions.

## Boot

```bash
cp deploy/.env.production.example deploy/.env.production
# Fill runtime secrets, exact HTTPS browser origin and model settings.
docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml up -d --build
```

The web port binds `127.0.0.1` by default. Keep the TLS terminator on that host, or set `SECFUSION_HTTP_BIND_ADDRESS` to its private, firewall-protected interface. Do not publish this plain-HTTP port directly to the Internet. Nginx carries the terminator's `X-Forwarded-Proto: https` to the API; the terminator must replace client-supplied forwarding headers. Long-running production services use `unless-stopped` so they return after a host reboot. Migration and artifact initialization remain one-shot jobs.

## Versioned release and recovery

Pin both application images to immutable release tags. Work from a clean checkout and save the tag and exact `deploy/.env.production` in a private release record. The tag is an operator coordinate; it must not imply a dirty worktree matches a Git commit.

```bash
test -z "$(git status --porcelain)"
release_tag="$(git rev-parse --short=12 HEAD)"
export SECFUSION_APP_IMAGE="secfusion-app:${release_tag}"
export SECFUSION_WEB_IMAGE="secfusion-product-web:${release_tag}"
compose=(docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml)
"${compose[@]}" config --quiet
"${compose[@]}" build api product-web
```

Before upgrading an existing deployment, save an access-controlled PostgreSQL dump and artifact archive. Redis roles can be rebuilt and do not replace either backup. On a first installation there is no previous database to dump.

```bash
umask 077
backup_tag="${release_tag}-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p .local/product-release-backups
"${compose[@]}" exec -T postgres pg_dump -U secfusion -Fc secfusion > ".local/product-release-backups/${backup_tag}.dump"
"${compose[@]}" exec -T api tar -C /var/lib/secfusion -cf - artifacts > ".local/product-release-backups/${backup_tag}.artifacts.tar"
"${compose[@]}" up -d --no-build
"${compose[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=5)"
"${compose[@]}" exec -T product-web wget -q -O- http://127.0.0.1/healthz
```

Accept the release only after both health reads and a real account sign-in, one Evidence read, one streamed answer, and a worker/collection observation succeed through the HTTPS browser origin. Keep the previous immutable images and backup until this check is complete. A successful `/health/ready` alone does not prove workers or model delivery.

If the new revision has not changed the database schema, set `SECFUSION_APP_IMAGE` and `SECFUSION_WEB_IMAGE` back to the previous tags and recreate only long-running services with `up -d --no-build --no-deps api scheduler task-event-dispatcher task-event-scheduler worker-collection worker product-web`; verify the same reads. If the schema changed or compatibility is uncertain, stop application writers, restore the matching PostgreSQL dump and artifact archive first, then start the previous image pair. Do not run the old `migrate` job against a newer schema or treat an image-only rollback as safe. Record old/new image tags, Alembic revisions, backup paths, health results and incident reason in a private operator release log. Keep backups and logs outside Git.

The product web image builds Vite with `/` as its base path. Nginx disables buffering for `/api/*`, so question-token and Investigation SSE remain streaming through the reverse proxy.

## Public boundary

Production `product-web` serves the public Product entry and account sign-in. Private Questions, sessions, Cases, Decisions and Task audit APIs require a server-owned account session; public WORLD and shared Evidence/Knowledge reads remain available. `/healthz` is available for container health checks. Configure `SECFUSION_AUTH_ALLOWED_ORIGINS` to the exact external browser origin, and terminate TLS in front of `product-web` before public access so production Secure session cookies work.

`X-Principal` remains an application principal coordinate, not authentication. The API resolves identity from an HttpOnly, Secure account-session cookie and checks Origin/CSRF on writes. A TLS terminator must pass the original scheme to Nginx and onward to FastAPI.

The browser entry serves the live product. Evaluation and competition records remain backend engineering capabilities; demo and frozen-proof navigation are not exposed in the application.

The product Nginx emits browser hardening headers (CSP, frame denial, no-sniff, no-referrer, and a restrictive Permissions-Policy). HSTS belongs to the TLS terminator because this container intentionally speaks plain HTTP behind that boundary; configure `Strict-Transport-Security` on the public HTTPS listener after the hostname and certificate are fixed.
