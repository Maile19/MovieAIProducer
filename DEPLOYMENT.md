# Deployment & Release Engineering Specification - MovieAIProducer

- **Project:** MovieAIProducer
- **Document ID:** DEPL-0001
- **Domain:** DevOps, Containerization, Continuous Delivery & Release Engineering
- **Version:** 2.0.0
- **Status:** Approved Production Specification
- **Canonical Architecture Decisions:** ADR-0014 (Deployment Strategy), ADR-0006 (Data Storage Strategy), ADR-0007 (Async Jobs), ADR-0012 (Asset Storage)
- **Production Host:** `https://producer.apologets.com`
- **Reverse Proxy & Ingress:** Traefik v3 / Nginx with Automated Let's Encrypt TLS

---

## 1. Deployment Vision & Architecture

MovieAIProducer utilizes an **Environment-Separated, Container-Ready Deployment Architecture** ensuring reproducible, zero-downtime releases from local developer workstations to the production deployment at `producer.apologets.com`.

### Core Engineering Invariants
1. **Immutable Artifacts:** Releases are packaged as immutable Docker images tagged with the Git commit SHA and Semantic Version (`movieai-backend:v2.0.0-<git_sha>`).
2. **Schema Migration Precedence:** Alembic database migrations (`alembic upgrade head`) run as an isolated pre-deployment job before new container traffic is admitted.
3. **Automated Health Gating:** Deployments verify the `/ready` probe (`backend/app/api/health.py`) for 60 seconds post-start before traffic shifting. If database or CAS asset checks fail, the deployment automatically rolls back.
4. **Decoupled API & Worker Scaling:** HTTP presentation containers (`web`) scale independently from heavy AI/GPU generation workers (`worker`), ensuring video rendering never starves user-facing API response times.

---

## 2. Production Topology & Deployment Flow

```mermaid
flowchart TD
    subgraph IngressLayer ["Public Ingress & DNS Layer"]
        DNS["DNS: producer.apologets.com"]
        Traefik["Traefik v3 Reverse Proxy (Port 443 / TLS 1.3)"]
        CertMgr["Let's Encrypt Automated ACME Certs"]
    end

    subgraph ServiceMesh ["Production Docker Compose Network"]
        subgraph WebTier ["Web Tier (FastAPI Presentation)"]
            Web1["movieai-web-1 (Uvicorn / FastAPI) [Port 8000]"]
            Web2["movieai-web-2 (Uvicorn / FastAPI) [Port 8000]"]
        end

        subgraph WorkerTier ["Worker Tier (Async GPU Orchestration)"]
            Worker1["movieai-worker-1 (Background Task Engine)"]
            Worker2["movieai-worker-2 (Local ComfyUI / GPT-SoVITS Bridge)"]
        end

        subgraph StorageTier ["Data Persistence & CAS Volumes"]
            PGDB[("PostgreSQL 16 DB (asyncpg) / SQLite (Dev)")]
            RedisQueue[("Redis 7 (Job Queue & Event Pub/Sub)")]
            AssetCASVolume[("Persistent NVMe Volume: ./data/assets")]
        end
    end

    DNS --> Traefik
    CertMgr --> Traefik
    Traefik -->|Round Robin HTTP| Web1
    Traefik -->|Round Robin HTTP| Web2

    Web1 -->|Readiness Probe /ready| Traefik
    Web2 -->|Readiness Probe /ready| Traefik

    Web1 --> PGDB
    Web2 --> PGDB
    Web1 --> RedisQueue
    Web2 --> RedisQueue
    Web1 --> AssetCASVolume
    Web2 --> AssetCASVolume

    Worker1 --> RedisQueue
    Worker2 --> RedisQueue
    Worker1 --> PGDB
    Worker2 --> PGDB
    Worker1 --> AssetCASVolume
    Worker2 --> AssetCASVolume
```

---

## 3. Environment Strategy Matrix

| Dimension | Local Development | Staging (`staging.producer.apologets.com`) | Production (`producer.apologets.com`) |
| :--- | :--- | :--- | :--- |
| **Runtime OS** | Linux / macOS / WSL2 | Ubuntu 22.04 LTS (Containerized) | Ubuntu 22.04 LTS (Docker Swarm / Compose) |
| **Python Tooling** | `uv` package manager (v0.5+) | `uv` in multi-stage Docker build | `uv` in multi-stage Docker build |
| **Database** | SQLite + `aiosqlite` (`./data/movieai.db`)| PostgreSQL 16 (`asyncpg`) | Managed PostgreSQL 16 with Read Replicas |
| **Asset Storage** | Local directory (`./data/assets`) | Local NVMe mounted volume | Encrypted NVMe Volume + S3/R2 Offsite Mirror |
| **Task Queue** | In-memory queue / Redis Local | Redis 7 container | Redis 7 High-Availability Sentinel |
| **AI Providers** | Mock adapters + Local ComfyUI / GPT-SoVITS | Staging API keys + Local GPU workers | Production API keys (Veo, Kling, ElevenLabs) |
| **Log Format** | Console colorized (`structlog`) | JSON formatted to stdout | Structured JSON shipped to Vector / Loki |
| **TLS / SSL** | Self-signed / Plain HTTP | Automated Let's Encrypt Staging | Production Automated Let's Encrypt TLS 1.3 |

---

## 4. Multi-Stage Dockerfile Specification

The production image uses a multi-stage build powered by the `uv` fast package manager to produce a minimal, hardened image (`< 180MB`):

```dockerfile
# Stage 1: Build stage with compiler tools and uv
FROM python:3.11-slim AS builder

WORKDIR /build

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:0.5.21 /uv /bin/uv

# Copy dependency manifests
COPY pyproject.toml uv.lock ./

# Compile virtual environment with production dependencies
RUN uv venv /opt/venv && \
    uv sync --frozen --no-dev

# Stage 2: Hardened production runtime
FROM python:3.11-slim AS runtime

WORKDIR /app

# Create non-root system user
RUN groupadd -g 1001 movieai && \
    useradd -u 1001 -g movieai -s /bin/bash -m movieai && \
    mkdir -p /app/data/assets /app/data/logs && \
    chown -R movieai:movieai /app

# Copy virtualenv from builder
COPY --from=builder --chown=movieai:movieai /opt/venv /opt/venv

# Copy application source and configuration
COPY --chown=movieai:movieai backend /app/backend
COPY --chown=movieai:movieai migrations /app/migrations
COPY --chown=movieai:movieai alembic.ini /app/alembic.ini

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED="1" \
    APP_ENV="production" \
    PORT=8000

USER movieai

EXPOSE 8000

# Health check using the grounded readiness endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/ready || exit 1

ENTRYPOINT ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## 5. Production Docker Compose Topology (`producer.apologets.com`)

```yaml
version: "3.8"

networks:
  movieai-net:
    driver: bridge

volumes:
  movieai-db-data:
  movieai-assets:
  traefik-certs:

services:
  traefik:
    image: traefik:v3.1
    container_name: movieai-traefik
    restart: always
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--entrypoints.web.http.redirections.entrypoint.to=websecure"
      - "--certificatesresolvers.letsencrypt.acme.tlschallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.email=ops@apologets.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik-certs:/letsencrypt
    networks:
      - movieai-net

  web:
    image: movieai-backend:v2.0.0
    restart: always
    env_file: .env.production
    environment:
      - APP_ENV=production
      - PUBLIC_BASE_URL=https://producer.apologets.com
      - ALLOWED_HOSTS=producer.apologets.com,127.0.0.1
      - DATABASE_URL=postgresql+asyncpg://movieai:secure_pass@postgres:5432/movieai_prod
      - ASSET_STORAGE_PATH=/app/data/assets
    volumes:
      - movieai-assets:/app/data/assets
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.movieai.rule=Host(`producer.apologets.com`)"
      - "traefik.http.routers.movieai.entrypoints=websecure"
      - "traefik.http.routers.movieai.tls.certresolver=letsencrypt"
      - "traefik.http.services.movieai.loadbalancer.server.port=8000"
    networks:
      - movieai-net

  worker:
    image: movieai-backend:v2.0.0
    restart: always
    entrypoint: ["python", "-m", "backend.app.worker"]
    env_file: .env.production
    volumes:
      - movieai-assets:/app/data/assets
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - movieai-net

  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_DB: movieai_prod
      POSTGRES_USER: movieai
      POSTGRES_PASSWORD: secure_pass
    volumes:
      - movieai-db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U movieai -d movieai_prod"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - movieai-net

  redis:
    image: redis:7-alpine
    restart: always
    command: ["redis-server", "--appendonly", "yes"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - movieai-net
```

---

## 6. Zero-Downtime Deployment & Migration Governance

### 6.1 Database Migration Protocol
1. **Pre-Deployment Execution:** Before launching the new container image, CI executes:
   ```bash
   alembic upgrade head
   ```
2. **Backward-Compatible Schema Invariant:**
   - Any new column must be `nullable=True` or have a server default.
   - Dropping columns or renaming tables follows a two-stage deprecation cycle (Expand -> Contract) across consecutive releases.

### 6.2 Rolling Shift & Rollback Runbook
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==> Step 1: Running Database Migrations"
docker compose run --rm web alembic upgrade head

echo "==> Step 2: Deploying New Web Container"
docker compose up -d --no-deps --build web

echo "==> Step 3: Verifying Readiness Probe on producer.apologets.com"
MAX_ATTEMPTS=12
ATTEMPT=0
UNTIL_HEALTHY=false

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://producer.apologets.com/ready || true)
  if [ "$STATUS" == "200" ]; then
    echo "Service is HEALTHY and READY."
    UNTIL_HEALTHY=true
    break
  fi
  echo "Waiting for readiness probe... attempt $((ATTEMPT+1))"
  sleep 5
  ATTEMPT=$((ATTEMPT+1))
done

if [ "$UNTIL_HEALTHY" != "true" ]; then
  echo "CRITICAL: Readiness check failed! Rolling back to previous container release."
  docker compose rollback web
  exit 1
fi

echo "==> Step 4: Updating Background Workers"
docker compose up -d --no-deps worker
echo "Deployment SUCCESSFUL."
```

---

## 7. Continuous Integration & Delivery Pipeline (CI/CD)

The GitHub Actions workflow enforces quality gates before any merge to `main`:

```yaml
name: CI/CD Production Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv and Setup Python
        uses: astral-sh/setup-uv@v3
        with:
          python-version: "3.11"
      - name: Install Dependencies
        run: uv sync --frozen
      - name: Architectural Layer Boundary Verification
        run: uv run pytest tests/architecture/test_layer_boundaries.py
      - name: Full Test Suite Execution
        run: uv run pytest tests/ --cov=backend
      - name: Alembic Migration Reversibility Check
        run: |
          uv run alembic upgrade head
          uv run alembic downgrade -1
          uv run alembic upgrade head

  build-and-deploy:
    needs: validate
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker Image
        run: docker build -t movieai-backend:${{ github.sha }} .
      - name: Deploy to producer.apologets.com via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.PROD_SERVER_IP }}
          username: deploy
          key: ${{ secrets.PROD_SSH_KEY }}
          script: |
            cd /opt/movieai-producer
            git pull origin main
            ./deploy.sh
```
