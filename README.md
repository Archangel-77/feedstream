# feedstream

> Production-grade real-time AIS maritime data ingestion, storage, querying, caching, and observability platform.

[![CI](https://github.com/Archangel-77/feedstream/actions/workflows/ci.yml/badge.svg)](https://github.com/Archangel-77/feedstream/actions/workflows/ci.yml)
[![Deploy](https://github.com/Archangel-77/feedstream/actions/workflows/deploy.yml/badge.svg)](https://github.com/Archangel-77/feedstream/actions/workflows/deploy.yml)
[![Uptime](https://img.shields.io/website?url=https%3A%2F%2Ffeedstream.fly.dev%2Fhealthz\&label=uptime)](https://feedstream.fly.dev)

## Live Environment

**Application:** [https://feedstream.fly.dev](https://feedstream.fly.dev)

**Interactive API Documentation:** [https://feedstream.fly.dev/docs](https://feedstream.fly.dev/docs)

**Health Endpoint:** [https://feedstream.fly.dev/healthz](https://feedstream.fly.dev/healthz)

**Architecture Documentation:** [ARCHITECTURE.md](ARCHITECTURE.md)

## Project Status

This project follows a six-week build plan (see [PLAN.md](PLAN.md)). Current progress:

| Week | Focus | Status |
| --- | --- | --- |
| 0 | Repo scaffold, CI, Postgres + Redis via Compose | ✅ |
| 1 | Vertical slice: API + worker + DB + first migration | ✅ |
| 2 | Worker hardening: dedup, retry/backoff, circuit breaker, graceful shutdown | ✅ |
| 3 | Query API: filters, cursor pagination, Redis caching, rate limiting | ✅ |
| 4 | Observability: Prometheus, Grafana, request tracing, `/debug/stats`, first ADR | ✅ |
| 5 | Fly.io deployment, retention job, production secrets | ✅ |
| 6 | Polish, ADRs, blog write-ups | 🔄 in progress |

---

# Overview

`feedstream` is a production-oriented backend system designed to ingest, process, store, and serve real-time maritime AIS (Automatic Identification System) vessel tracking data.

Unlike traditional CRUD portfolio projects, feedstream focuses on the operational concerns that real-world backend engineers encounter daily:

* Continuous ingestion of external event streams
* Fault tolerance and recovery
* Idempotent processing
* Query performance at scale
* Caching strategies
* Service observability
* Production deployment
* Data retention management
* Monitoring and diagnostics

The project was intentionally designed to resemble a service that could run continuously in production rather than a demonstration application.

---

# Why AIS Maritime Data?

AIS (Automatic Identification System) is used worldwide by vessels to broadcast information such as:

* Vessel identity
* Position
* Heading
* Speed
* Navigation status
* Voyage information

AIS streams create an excellent backend engineering problem because they are:

* Real-time
* High volume
* Continuously generated
* Operationally important
* Prone to duplicate and replay events
* Sensitive to network interruptions

This makes AIS data a significantly more realistic engineering challenge than commonly used portfolio datasets such as weather feeds, cryptocurrency prices, or static datasets.

---

# Project Goals

The primary objective of feedstream is to demonstrate competence across the complete backend engineering lifecycle:

## Data Ingestion

Consume real-time maritime events from an external upstream source.

## Persistence

Store events durably with strong consistency guarantees.

## Reliability

Remain operational despite:

* Network interruptions
* Upstream instability
* Process restarts
* Duplicate events

## Performance

Provide low-latency query endpoints through:

* Database indexing
* Efficient pagination
* Redis caching

## Observability

Expose meaningful telemetry through:

* Metrics
* Structured logs
* Request tracing
* Operational dashboards

## Deployment

Run as a publicly accessible cloud service with automated deployment workflows.

---

# Quickstart

Get the service running locally in under five minutes.

```bash
# 1. Clone and enter
git clone https://github.com/Archangel-77/feedstream.git
cd feedstream

# 2. Start Postgres + Redis (and optionally Prometheus + Grafana)
docker compose up -d postgres redis

# 3. Install with dev extras
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 4. Apply database migrations
alembic upgrade head

# 5. Run the API (terminal 1)
uvicorn feedstream.main:app --reload

# 6. Run the ingestion worker (terminal 2)
python -m feedstream.worker
```

Once running, the service is available at:

| URL | Purpose |
| --- | --- |
| http://localhost:8000/ | Landing page |
| http://localhost:8000/docs | Interactive Swagger UI |
| http://localhost:8000/healthz | Liveness probe |
| http://localhost:8000/metrics | Prometheus scrape target |
| http://localhost:3000 | Grafana (admin / admin) |
| http://localhost:9090 | Prometheus |

> The worker requires an `AIS_API_KEY` for the upstream WebSocket feed. Without it the worker will log authentication errors and stay disconnected — the API and tests still work.

---

# Configuration

All runtime configuration is loaded via [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) from environment variables (or a local `.env` file in development). Production secrets are injected through the Fly.io secret store — never committed.

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://feedstream:feedstream@localhost:5433/feedstream` | Async SQLAlchemy DSN |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis DSN (DB 0 for cache, DB 1 for rate-limit storage) |
| `AIS_API_KEY` | *(empty)* | API key for the upstream AIS WebSocket feed |
| `APP_ENV` | `development` | `development` / `staging` / `production` |
| `LOG_LEVEL` | `INFO` | Application log level |
| `DEBUG_STATS_TOKEN` | `local-dev-token` | Bearer-style token required to call `/debug/stats` |
| `ENABLE_METRICS` | `true` | Expose the `/metrics` endpoint |
| `ENABLE_DOCS` | `true` | Expose `/docs`, `/redoc`, and `/openapi.json` |
| `RETENTION_DAYS` | `30` | Events older than this are purged by the retention job |
| `RETENTION_BATCH_SIZE` | `5000` | Maximum rows deleted per retention run |
| `RETENTION_INTERVAL_MINUTES` | `1440` | How often the retention job runs |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Used in OpenAPI server URL |
| `GITHUB_REPO_URL` | `https://github.com/Archangel-77/feedstream` | Linked from the landing page |

---

# Core Features

## Real-Time Event Ingestion

A dedicated worker process connects to the AIS stream and continuously receives incoming vessel events.

Features include:

* Async event processing
* Continuous stream consumption
* Event normalization
* Database persistence
* Clean shutdown handling
* Operational metrics

The worker operates independently from the API service, preventing ingestion failures from affecting user-facing endpoints.

---

## Idempotent Event Processing

Duplicate events are inevitable in distributed systems.

Feedstream prevents duplicate storage using:

* Deterministic `dedup_key`
* PostgreSQL unique constraints
* `ON CONFLICT DO NOTHING`

This ensures that:

* Replayed events are ignored
* Worker restarts remain safe
* Network retries do not create duplicate rows

Example:

```sql
INSERT INTO events (...)
ON CONFLICT (dedup_key) DO NOTHING;
```

---

## Resilient Connectivity

External systems fail.

The ingestion worker includes:

### Exponential Backoff

Reconnect attempts gradually increase delay between retries.

Benefits:

* Prevents retry storms
* Reduces upstream pressure
* Improves system stability

### Jitter

Randomized retry delays prevent synchronized reconnect behavior.

### Circuit Breaker

Repeated upstream failures trigger a temporary pause period before additional connection attempts are made.

Benefits:

* Prevents endless failure loops
* Protects upstream resources
* Creates predictable recovery behavior

---

## Graceful Shutdown

When the process receives a termination signal:

1. Stop accepting new work
2. Complete current batch processing
3. Flush pending writes
4. Close connections cleanly
5. Exit safely

This prevents:

* Partial writes
* Lost events
* Corrupted state

---

# API

Feedstream exposes a FastAPI-powered REST interface. All routes are tagged `ops` (operational) or `events` (data) in the OpenAPI schema.

## Endpoints

| Method | Path | Auth | Rate Limit | Purpose |
| --- | --- | --- | --- | --- |
| `GET` | `/` | none | n/a | Landing page (HTML) |
| `GET` | `/healthz` | none | 1000 / hour | Liveness probe |
| `GET` | `/events` | none | 100 / minute | Query events with filters and cursor pagination |
| `GET` | `/metrics` | none (prod: IP-restricted) | 1000 / hour | Prometheus scrape target |
| `GET` | `/debug/stats` | `X-Debug-Token` header | 1000 / hour | Worker state, cache stats, DB pool stats |
| `GET` | `/docs` | n/a | 1000 / hour | Interactive Swagger UI (`ENABLE_DOCS=true`) |
| `GET` | `/redoc` | n/a | 1000 / hour | ReDoc UI (`ENABLE_DOCS=true`) |
| `GET` | `/openapi.json` | n/a | 1000 / hour | OpenAPI 3.x schema (`ENABLE_DOCS=true`) |

Rate limits are enforced with [slowapi](https://github.com/laurentS/slowapi), backed by Redis (DB 1) so limits are shared across API replicas.

---

## Health Check

```http
GET /healthz
```

Used by:

* Load balancers
* Deployment platforms
* Monitoring systems

---

## Event Queries

```http
GET /events
```

Supports filtering by:

* Source
* Event type
* Time range

Example:

```http
GET /events?source=ais&limit=100
```

Real response shape:

```bash
curl "https://feedstream.fly.dev/events?limit=1"
```

```json
{
  "events": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "source": "aisstream",
      "event_type": "PositionReport",
      "payload": {
        "MessageType": "PositionReport",
        "MetaData": {
          "MMSI": 257012340,
          "time_utc": "2026-07-22 10:14:02"
        },
        "Message": {
          "Latitude": 51.95,
          "Longitude": 4.12,
          "SOG": 12.4,
          "COG": 87.5
        }
      },
      "received_at": "2026-07-22T10:14:02Z",
      "dedup_key": "mmsi:257012340:PositionReport:2026-07-22 10:14:02"
    }
  ],
  "next_cursor": "MjAyNi0wNy0yMlQxMDoxNDowMjo1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDA=",
  "has_more": true,
  "total_count": 1500
}
```

---

## Cursor-Based Pagination

Instead of offset pagination:

```http
?page=500
```

Feedstream uses cursor pagination:

```http
?cursor=abc123
```

Benefits:

* Consistent performance
* Stable ordering
* Better scalability
* Reduced database overhead

---

## OpenAPI Documentation

FastAPI automatically generates interactive documentation.

Features include:

* Endpoint descriptions
* Request schemas
* Response schemas
* Example payloads
* Validation rules

Available at:

```text
/docs
```

---

# Data Model

The core storage entity is the Event model.

```text
Event
├── id
├── source
├── event_type
├── payload
├── received_at
└── dedup_key
```

Field descriptions:

| Field       | Purpose                  |
| ----------- | ------------------------ |
| id          | Internal identifier      |
| source      | Event source             |
| event_type  | AIS event category       |
| payload     | Original event data      |
| received_at | Ingestion timestamp      |
| dedup_key   | Duplicate prevention key |

---

# Caching Strategy

Feedstream uses Redis to reduce database load on frequently requested queries.

## Cache Workflow

Request arrives

↓

Check Redis

↓

Cache hit → return cached response

OR

↓

Cache miss → query PostgreSQL

↓

Store result in Redis

↓

Return response

---

## Cache Invalidation

When new events are stored:

* Relevant cache entries are invalidated
* Fresh queries rebuild cache state

This balances:

* Performance
* Data freshness
* Operational simplicity

---

# Observability

One of the primary goals of feedstream is operational visibility.

Every major component exposes telemetry.

---

## Metrics

Prometheus metrics include:

### Ingestion Metrics

* Events ingested
* Events rejected
* Event latency

### API Metrics

* Request count
* Request duration
* Response status codes

### Cache Metrics

* Cache hits
* Cache misses
* Cache invalidations

### Worker Metrics

* Connected state
* Retry state
* Circuit breaker state

### Database Metrics

* Pool utilization
* Query latency

---

## Prometheus

Metrics endpoint:

```http
GET /metrics
```

Prometheus periodically scrapes:

* API metrics
* Worker metrics
* System health indicators

---

## Grafana Dashboards

Grafana provides visualization for:

* Event throughput
* Query latency
* Error rates
* Retry frequency
* Cache performance
* Database health

The dashboard JSON is committed under [`ops/grafana/dashboards/feedstream.json`](ops/grafana/dashboards/feedstream.json) and is auto-provisioned by Grafana on first boot — see [Quickstart](#quickstart) for the local URL.

---

## Structured Logging

Feedstream uses structured JSON logging via [`python-json-logger`](https://github.com/nhairs/python-json-logger). Every log record contains:

```json
{
  "timestamp": "...",
  "level": "INFO",
  "event": "event_ingested",
  "correlation_id": "..."
}
```

Benefits:

* Machine-readable logs
* Better searchability
* Easier incident investigation

---

## Request Tracing

Each request receives a unique identifier.

Example:

```text
X-Request-ID: 4f5f7f8f...
```

The identifier propagates through:

* API logs
* Worker logs
* Error reports

This enables end-to-end traceability.

---

# Security

Feedstream follows basic production security practices.

## Secrets Management

Secrets are never committed.

Production secrets are loaded from:

* Fly.io secret store
* Environment variables

---

## Rate Limiting

Public endpoints are protected against abuse through request rate limits.

Benefits:

* Protects infrastructure
* Prevents scraping
* Reduces accidental overload

---

## Protected Diagnostics

Administrative endpoints require authentication.

Examples:

```http
GET /debug/stats
```

These endpoints expose:

* Worker state
* Cache statistics
* Internal metrics

---

# Data Retention

AIS streams generate data continuously.

Without retention policies, storage grows indefinitely.

Feedstream includes scheduled cleanup jobs that:

* Remove old records
* Control database growth
* Maintain predictable operational costs

Retention rules are configurable.

---

# Technology Stack

## Backend

* Python 3.10+
* [FastAPI](https://fastapi.tiangolo.com/) (async)
* [SQLAlchemy 2.x](https://docs.sqlalchemy.org/) with the async asyncpg driver
* [Pydantic v2](https://docs.pydantic.dev/) and `pydantic-settings`
* [uvicorn](https://www.uvicorn.org/) ASGI server

## Ingestion

* [`websockets`](https://websockets.readthedocs.io/) for the upstream AIS WebSocket
* [`tenacity`](https://tenacity.readthedocs.io/) for retry with exponential backoff + jitter
* In-process circuit breaker (see [`CircuitBreaker` in `worker.py`](src/feedstream/worker.py))

## Storage

* PostgreSQL 16 (Alembic-managed schema, `ON CONFLICT (dedup_key) DO NOTHING` for idempotency)
* Redis 7 (response cache with TTL, plus DB 1 for rate-limit storage)

## API and Resilience

* [`slowapi`](https://github.com/laurentS/slowapi) for Redis-backed per-endpoint rate limiting
* Cursor-based pagination over `(received_at, id)` for stable ordering

## Observability

* [Prometheus](https://prometheus.io/) (`prometheus-client`) metrics exposed at `/metrics`
* [Grafana](https://grafana.com/) dashboard provisioned from `ops/grafana/dashboards/`
* Structured JSON logging via `python-json-logger`
* Request-ID propagation middleware for end-to-end correlation

## Infrastructure

* Docker + Docker Compose for local Postgres, Redis, Prometheus, and Grafana
* [Fly.io](https://fly.io) for production hosting (two processes: `app` and `retention`)

## Tooling

* [Pytest](https://docs.pytest.org/) + `pytest-asyncio` + `httpx`
* [Ruff](https://docs.astral.sh/ruff/) (lint + format)
* [MyPy](https://mypy.readthedocs.io/) (lenient)
* [Alembic](https://alembic.sqlalchemy.org/) for schema migrations
* GitHub Actions for CI and deployment
* [Pre-commit](https://pre-commit.com/) for local hooks

---

# Deployment

The service is deployed to [Fly.io](https://fly.io) in the `ams` region. Configuration lives in [`fly.toml`](fly.toml); the production image is built from the repo's [`Dockerfile`](Dockerfile).

## Process layout

Fly runs two processes from a single image:

| Process | Command | Purpose |
| --- | --- | --- |
| `app` | `uvicorn feedstream.main:app --host 0.0.0.0 --port 8080` | Public FastAPI service |
| `retention` | `python -m feedstream.retention` | Periodic row-purge job |

The retention process is intentionally separate from `app` so it can be scaled and restarted independently.

## Health checks

Fly performs an HTTP check against `/healthz` every 10 seconds with a 2-second timeout and 10-second grace period. A failing check triggers a new release of the `app` process.

## Secrets

Production secrets are managed with `fly secrets set` and injected as environment variables. Nothing sensitive is checked in. The full set of variables is documented in [Configuration](#configuration).

## Migrations

`alembic upgrade head` runs as part of the deploy workflow (`.github/workflows/deploy.yml`) before the new release is started, so the schema is always ahead of the running code.

## Observability in production

* `/metrics` is exposed and scraped by an external Prometheus (hosted alongside the app on Fly).
* Grafana dashboards are provisioned from `ops/grafana/dashboards/feedstream.json`.
* Structured JSON logs are written to stdout and aggregated by Fly's log shipper.

## Production overrides

The following defaults are flipped in production (`APP_ENV=production`):

* `ENABLE_DOCS=false` — `/docs`, `/redoc`, and `/openapi.json` return 404
* `ENABLE_METRICS=true` — `/metrics` is reachable on the internal port and scrape target
* `LOG_LEVEL=INFO`
* `RETENTION_DAYS=30`, `RETENTION_INTERVAL_MINUTES=1440`

---

# Local Development

## Clone Repository

```bash
git clone https://github.com/Archangel-77/feedstream.git
cd feedstream
```

## Start Infrastructure

```bash
docker compose up -d postgres redis
```

## Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Run Migrations

```bash
alembic upgrade head
```

## Start API

```bash
uvicorn feedstream.main:app --reload
```

## Start Worker

```bash
python -m feedstream.worker
```

---

# Testing

Feedstream treats testing as a first-class feature. Every test file under `tests/` maps to a real production concern.

| Test file | Covers |
| --- | --- |
| `test_health.py` | `/healthz` liveness behavior |
| `test_events.py` | `/events` filtering, cursor pagination, validation, response schema |
| `test_cache.py` | Redis cache hits, misses, TTL, and write-side invalidation |
| `test_rate_limit.py` | slowapi + Redis-backed rate limiting on `ops` and `events` tags |
| `test_metrics.py` | `/metrics` output and Prometheus client wiring |
| `test_tracing.py` | Request-ID propagation middleware |
| `test_worker.py` | Ingestion function, dedup, retry, circuit breaker, graceful shutdown |
| `test_retention.py` | Retention job deletes only expired rows, batch size honored |
| `test_debug_stats.py` | `/debug/stats` token auth and payload shape |
| `test_landing.py` | `/` landing page renders with correct links |

Fixtures in `tests/conftest.py` provide an isolated SQLite-backed test database, a fake Redis stub, and pre-seeded events — tests run with no external services required.

Run tests:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=feedstream --cov-report=term-missing
```

---

# CI/CD

Every push triggers automated validation.

Pipeline stages:

1. Ruff linting
2. MyPy type checking
3. Pytest execution
4. Deployment workflow

This guarantees that broken code cannot be deployed accidentally.

---

# Architecture

End-to-end view of the system:

```mermaid
flowchart LR
    subgraph Upstream
        A[AIS WebSocket Stream]
    end

    subgraph Ingestion
        B[Worker Process]
        CB[Circuit Breaker]
        RT[Retry + Backoff]
    end

    subgraph Storage
        C[(PostgreSQL)]
        D[(Redis Cache)]
    end

    subgraph API
        E[FastAPI Service]
    end

    subgraph Observability
        P[Prometheus]
        G[Grafana]
    end

    A --> B
    B --> RT
    RT --> CB
    CB --> C
    B --> D
    E --> C
    E --> D
    E --> P
    B --> P
    P --> G
    F[Client] --> E
```

**Data flow**

1. Worker consumes AIS events from the upstream WebSocket feed.
2. Worker normalizes the event and computes a deterministic `dedup_key`.
3. Worker writes to Postgres with `INSERT ... ON CONFLICT (dedup_key) DO NOTHING`.
4. Worker invalidates the affected Redis cache keys after successful writes.
5. API queries Postgres and returns cursor-paginated, filtered responses.
6. API caches hot query responses in Redis with a 5-minute TTL.
7. Prometheus scrapes `/metrics` from both API and worker; Grafana visualizes trends.

For the full component breakdown, reliability patterns, and trade-offs see:

* [ARCHITECTURE.md](ARCHITECTURE.md)
* [docs/adr/](docs/adr/)

---

# Design Decisions

Key architectural choices include:

| Decision                      | Reason                                |
| ----------------------------- | ------------------------------------- |
| Separate worker process       | Isolation between ingestion and API   |
| PostgreSQL as source of truth | Reliability and query capability      |
| Redis caching                 | Reduced latency and database pressure |
| Cursor pagination             | Better scaling characteristics        |
| Prometheus + Grafana          | Industry-standard observability       |
| Structured logging            | Easier diagnostics and debugging      |
| Fly.io deployment             | Simple production hosting             |

Detailed explanations are available in the ADR documents.

---

# Known Limitations and Trade-offs

Decisions made in the interest of simplicity, with the cost acknowledged up front.

| Decision | Trade-off |
| --- | --- |
| **Single ingestion worker** | No consumer-group semantics. Horizontal scaling would require partitioning the upstream by MMSI range or migrating to a broker (Kafka, NATS). Easy to add later. |
| **Cache TTL of 5 minutes** | `/events` responses may be up to 5 minutes stale after a new write. Invalidation is best-effort; the TTL is the safety net. Acceptable because every response is anchored to a `received_at` timestamp the client can re-check. |
| **Cursor pagination** | More complex than offset pagination for both client and server. Chosen because offset performance degrades on large tables and produces unstable results under concurrent writes. |
| **Cursor format is base64-encoded `received_at:id`** | Tied to a single sort order. If the API ever supports sorting by other columns, the cursor must be redesigned (e.g. a JSON envelope). |
| **In-process circuit breaker** | State is per-process, so each Fly machine maintains its own breaker. Acceptable because the breaker is short-lived (default 60 s). For multi-replica correctness, move it to Redis. |
| **Postgres as the only durable store** | No read replica. If the query load grows, the API process and retention job will compete for the same primary connection pool. |
| **`ENABLE_DOCS=false` in production** | Saves a few KB and hides the schema. If you want docs in prod, flip it and protect `/docs` behind the same token as `/debug/stats`. |

---

# Roadmap

Ideas considered for a future iteration, ordered roughly by impact:

| Area | Idea | Notes |
| --- | --- | --- |
| Query | Geographic bounding-box filters (`?bbox=lat1,lon1,lat2,lon2`) | Natural fit for the AIS payload; needs a GIST index |
| Query | Time-bucketed aggregates (`/events/stats?bucket=1h`) | Reduces load on long time-range scans |
| Throughput | Multi-worker ingestion with a real broker (Kafka / NATS) | Today's single worker is the bottleneck above ~1k events/s |
| Throughput | Read replica for the API process | Decouples query load from retention writes |
| Cache | Move circuit-breaker state into Redis | Required before scaling to more than one worker replica |
| Streaming | WebSocket or SSE push endpoint for new events | Complements the current poll-based `/events` |
| Analytics | Vessel movement aggregation and dwell-time analytics | Separate read model, can be backed by hourly rollups |
| Operations | Alerting rules in Grafana (e.g. ingestion flatline, error rate spike) | Closes the observability loop |

---

# Portfolio Value

Feedstream was intentionally designed to demonstrate backend engineering competencies that extend beyond CRUD applications.

The project showcases:

* Distributed systems fundamentals
* Reliability engineering
* Observability practices
* Cloud deployment
* Operational thinking
* API design
* Data engineering concepts

It is designed to answer a common interview question:

> “Can this person build and operate a real service?”

Feedstream is the practical demonstration of that capability.

---

# License

MIT License

See `LICENSE` for details.

This version is substantially stronger for recruiters and hiring managers because it explains not only *what* the project does, but also *why each engineering decision exists* and *what problems it solves*.
