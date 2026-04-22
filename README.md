# feedstream

![Status](https://img.shields.io/badge/status-in%20development-yellow)
![CI](https://github.com/YOUR_USERNAME/feedstream/actions/workflows/ci.yml/badge.svg)

A real-time data ingestion and query service built on live AIS maritime ship-tracking data.

## What it does

feedstream connects to the global AIS (Automatic Identification System) stream, ingests real-time ship position and status messages, persists them to a Postgres database, and exposes them through a query HTTP API. The service is designed for correctness under load: idempotent ingestion, graceful reconnection, cursor-based pagination, Redis caching, and full Prometheus observability.

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + async SQLAlchemy |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Ingestion | asyncio worker via aisstream.io WebSocket |
| Observability | Prometheus + Grafana |
| Infra | Docker Compose / Fly.io |
| CI | GitHub Actions |

## Roadmap

- [ ] **Week 0** — Project scaffold, CI pipeline, Postgres + Redis in Docker
- [ ] **Week 1** — Vertical slice: AIS source → database → HTTP response
- [ ] **Week 2** — Worker hardening: dedup, backoff, circuit breaker, structured logging
- [ ] **Week 3** — Query API: filtering, cursor pagination, Redis caching, rate limiting
- [ ] **Week 4** — Observability: Prometheus metrics, Grafana dashboard, request tracing
- [ ] **Week 5** — Deployment: live on Fly.io, retention policy, status badge
- [ ] **Week 6** — Polish: architecture docs, ADRs, blog post

## Running locally

```bash
# Start Postgres and Redis
docker compose up -d

# Copy and fill in your env vars
cp .env.example .env

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## Data source

AIS (Automatic Identification System) is the maritime tracking standard used by all large vessels. Ships broadcast their position, speed, heading, and status on VHF radio; the global feed is aggregated and exposed as a WebSocket stream by [aisstream.io](https://aisstream.io). This project ingests that stream in real time.
