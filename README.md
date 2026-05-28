# feedstream

![Status](https://img.shields.io/badge/status-in%20development-yellow)
![CI](https://github.com/Archangel-77/feedstream/actions/workflows/ci.yml/badge.svg)

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

- [x] **Week 0** — Project scaffold, CI pipeline, Postgres + Redis in Docker
- [x] **Week 1** — Vertical slice: AIS source → database → HTTP response
- [x] **Week 2** — Worker hardening: dedup, backoff, circuit breaker, structured logging
- [x] **Week 3** — Query API: filtering, cursor pagination, Redis caching, rate limiting
- [ ] **Week 4** — Observability: Prometheus metrics, Grafana dashboard, request tracing
- [ ] **Week 5** — Deployment: live on Fly.io, retention policy, status badge
- [ ] **Week 6** — Polish: architecture docs, ADRs, blog post

## API Documentation

Interactive API documentation is available at `/docs` (Swagger UI) and `/redoc` (ReDoc) when running the service.

### Swagger Preview

![Swagger UI preview](docs/images/swagger-ui.png)

### Key Features

- **Advanced Filtering**: Filter by source, event type, and time ranges
- **Cursor-based Pagination**: Efficient navigation through large datasets
- **Redis Caching**: 5-minute cache with automatic invalidation on new data
- **Rate Limiting**: 100 requests/minute for events, 1000/hour for operations
- **Comprehensive Examples**: Rich OpenAPI documentation with sample requests/responses

### Caching Strategy

The API implements a multi-layer caching strategy to optimize performance:

1. **Query Result Caching**: All `/events` responses are cached for 5 minutes based on query parameters
2. **Cache Key Generation**: Includes all filters, pagination, and sorting parameters
3. **Automatic Invalidation**: Cache is cleared when new events are written to the database
4. **Pattern-based Clearing**: Uses `events:*` pattern for efficient bulk invalidation

This approach balances data freshness with performance, ensuring users get fast responses while seeing new data within minutes.

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

# Start the API server
uvicorn feedstream.main:app --reload
```

## Data source

AIS (Automatic Identification System) is the maritime tracking standard used by all large vessels. Ships broadcast their position, speed, heading, and status on VHF radio; the global feed is aggregated and exposed as a WebSocket stream by [aisstream.io](https://aisstream.io). This project ingests that stream in real time.
