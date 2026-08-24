# LinkedIn post — draft

## Short version

I built a real-time backend platform for maritime AIS vessel tracking, and it's live: <https://feedstream.fly.dev>

The interesting part wasn't reading a stream and writing rows — it was behaving correctly when things go wrong:

- Replayed events are deduplicated at the database level (`ON CONFLICT DO NOTHING`) — restarts and network retries never create duplicates.
- A circuit breaker + exponential backoff with jitter stops retry storms when the upstream drops.
- Cursor pagination and Redis caching (with write-side invalidation) keep queries fast under load.
- Prometheus + Grafana make all of it visible.

Built with Python, FastAPI, PostgreSQL, Redis, Prometheus, Grafana, Docker. Deployed on Fly.io with CI/CD and a data retention job.

#python #backend #fastapi #postgresql #redis #observability #devops

## Longer variant (optional)

Add 2–3 sentences about the hardest bug you fixed (e.g. "The moment it clicked was when a replay of the WebSocket feed created duplicate rows — that's when I moved dedup from the app into the database uniqueness constraint.") and link the repo.
