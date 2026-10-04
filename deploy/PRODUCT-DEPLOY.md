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
# fill secrets
docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml up -d --build
```

The product web image builds Vite with `/` as its base path. Nginx disables buffering for `/api/*`, so Investigation SSE can remain streaming through the reverse proxy.

## Public boundary

Do not expose a competition/demo instance broadly until an explicit access-control layer is configured. `X-Principal` is an application principal coordinate, not authentication. When a hostname is available, terminate TLS in front of `product-web` or extend this Nginx layer with the selected certificate workflow.
