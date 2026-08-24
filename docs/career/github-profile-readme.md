# GitHub profile README — draft

Create a repo named `<username>/<username>` and put this in its `README.md` to make it your profile intro.

## Draft

```markdown
### Hi, I'm [Your Name] 👋

Backend engineer focused on reliability, data ingestion, and observability.

**Featured project: [feedstream](https://github.com/Archangel-77/feedstream)** — live at <https://feedstream.fly.dev>

A production-grade, real-time maritime AIS ingestion platform:

- **Ingestion** — resilient WebSocket worker with idempotent writes (deterministic `dedup_key` + `ON CONFLICT DO NOTHING`), exponential backoff, and a circuit breaker
- **API** — FastAPI with filtering, cursor pagination, Redis caching (5-min TTL + write-side invalidation), and Redis-backed rate limiting
- **Observability** — Prometheus metrics, a provisioned Grafana dashboard, and structured JSON logs with request correlation IDs
- **Ops** — deployed to Fly.io, Alembic migrations, a scheduled retention job, and GitHub Actions CI/CD

Built with Python · FastAPI · PostgreSQL · Redis · Prometheus · Grafana · Docker
```

## Pin steps

1. Open your profile → **Customize your pins**.
2. Pin `feedstream`.
3. (Optional) Add the live demo URL to the repo's topics/description.
