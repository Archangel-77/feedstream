# CV bullets — feedstream

## Project summary line

**feedstream — Real-Time AIS Maritime Data Platform** (Python · FastAPI · PostgreSQL · Redis · Prometheus · Grafana · Docker · Fly.io)

A production-style backend service that ingests live vessel-tracking data from an upstream WebSocket feed, stores it idempotently, and serves low-latency filtered queries. Deployed live at <https://feedstream.fly.dev>.

## Impact bullets

- Built resilient real-time ingestion with idempotent writes (deterministic `dedup_key` + `INSERT … ON CONFLICT DO NOTHING`) and a circuit breaker, so replays and worker restarts never create duplicate rows.
- Implemented cursor pagination, Redis caching with write-side invalidation, and Redis-backed rate limiting, reducing database load on the hot `/events` endpoint.
- Added Prometheus/Grafana observability — ingestion, query-latency, worker-state, cache, and DB-pool metrics — plus structured JSON logs with request correlation IDs, and deployed to Fly.io with automated CI/CD and a scheduled retention job.

## Supporting facts (add when you can)

- 44 tests across 10 test files; CI (ruff, mypy, pytest) green on every push.
- 5 Architecture Decision Records documenting key trade-offs.
- Interactive API docs served live at <https://feedstream.fly.dev/docs>.
