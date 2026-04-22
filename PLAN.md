# `feedstream` — 6-Week Build Plan

> A real-time data ingestion & query service. Backend + data-adjacent portfolio project designed to get interviews, not stars.

---

## Ground rules (these matter more than the plan itself)

**1. Commit discipline is non-negotiable.** Target 8–15 small commits per week, each one a single logical change with a clear message. "Add reconnection backoff to ingestion worker" — yes. "WIP updates" — no. If you find yourself about to make a commit with more than ~150 lines changed across unrelated concerns, split it.

**2. Push to `main` daily, even if incomplete.** A repo that shows activity every 2–3 days for 6 weeks is visually striking on a GitHub profile. Dead weeks look bad.

**3. Tests grow with the code, not at the end.** Every week's features land with their tests. This is the single biggest signal of professional discipline that a hiring manager sees in your code.

**4. The README evolves too.** Don't write it once at the end. Start it Week 1 with just the goal and update it as you build. By Week 6 it'll be real, not reverse-engineered.

**5. Pick your data source now, not later.** This is your Week 0 decision. Do not start coding without it. Recommendations at the bottom.

**6. If you fall behind, cut scope from the *last* week, not the middle ones.** The middle weeks are where the depth lives.

---

## Week 0 — Setup (this weekend, 4–6 hours)

**Goal:** Decisions made, skeleton pushed, CI green. No feature code yet.

- [ ] Pick your ingestion source (see bottom). Write a one-paragraph "why this source" in the README.
- [ ] Create the repo. Public from day one. Name: `feedstream` (or whatever you like — just don't call it `feedstream-demo`, that undersells it).
- [ ] Initialise Python project with `pyproject.toml`, `ruff`, `pytest`, `mypy` (even if loose initially), and a `.pre-commit-config.yaml`.
- [ ] Set up GitHub Actions: one workflow that runs lint + type check + pytest on every push. This must be green before Week 1 starts.
- [ ] Create `docker-compose.yml` with Postgres and Redis services. No app service yet.
- [ ] Write the initial README: 1 paragraph on the goal, 1 paragraph on the stack, a "Status: in development" badge, a roadmap section listing the six weeks as checkboxes.
- [ ] First commits, in order: `init: project scaffold`, `ci: lint + test pipeline`, `infra: postgres + redis compose`, `docs: initial readme and roadmap`.

**End-of-week check:** Repo exists, CI is green, README states intent clearly, no code you'll be embarrassed by in Week 6.

---

## Week 1 — Vertical slice (15–20 hours)

**Goal:** End-to-end path from upstream source → database → HTTP response. Ugly but working.

- [ ] FastAPI app skeleton with health endpoint (`/healthz`) and settings loaded from environment (use `pydantic-settings`).
- [ ] Async SQLAlchemy setup with one model: `Event` (id, source, event_type, payload JSONB, received_at, dedup_key).
- [ ] Alembic configured, one initial migration.
- [ ] Ingestion worker as a separate process (not a FastAPI background task — this matters). Use `asyncio` with a clean shutdown handler. It connects to your source, reads events, writes to Postgres. Naively for now — no dedup, no backoff.
- [ ] One query endpoint: `GET /events?limit=50` that returns the most recent events.
- [ ] Tests: one for the health endpoint, one for the query endpoint against a test database, one that feeds a fake event to the ingestion function and asserts it lands in the DB.

**Target commits (~10):** scaffold app, add settings, add Event model, add first migration, add worker skeleton, implement naive ingestion, add query endpoint, add test fixtures, add health test, add query endpoint test.

**End-of-week check:** Run `docker compose up` on a clean machine, worker starts, data flows in, `curl localhost:8000/events` shows real rows. Screenshot it for yourself — you'll want it later.

---

## Week 2 — Hardening the worker (15–20 hours)

**Goal:** The worker survives reality. This is where the project starts being interesting.

- [ ] Add a `dedup_key` unique index and implement idempotent inserts (Postgres `ON CONFLICT DO NOTHING`). Write a test that ingests the same event twice and asserts only one row exists.
- [ ] Add reconnection logic with exponential backoff + jitter when the upstream drops. Use a library (`tenacity`) — don't hand-roll. Write a test using a fake source that fails N times before succeeding.
- [ ] Add graceful shutdown: the worker catches SIGTERM, finishes its current batch, flushes pending writes, exits cleanly. Test it.
- [ ] Add structured logging with `structlog` or `python-json-logger`. Every log line: timestamp, level, event, correlation_id. No more `print()` anywhere.
- [ ] Add a basic circuit breaker: if the upstream fails more than X times in Y seconds, pause for Z before retrying. This is the kind of detail that makes a senior dev nod.

**Target commits (~12):** add dedup constraint, implement idempotent insert, add dedup test, add retry with backoff, add retry tests, add graceful shutdown handler, add shutdown test, switch to structlog, add correlation ids, add circuit breaker, add circuit breaker tests, README update.

**End-of-week check:** Kill the upstream manually (if it's your own fake feed) or toggle airplane mode — worker should reconnect cleanly. Restart the worker mid-ingestion — no duplicates. Send SIGTERM — it exits gracefully. If any of these don't work, fix them before moving on.

---

## Week 3 — Query API + caching (15–20 hours)

**Goal:** The HTTP layer becomes real. Where performance and API design get shown off.

- [ ] Expand the query API: filters (by source, event_type, time range), cursor-based pagination (not offset — offset is a junior smell), sort order.
- [ ] Add Pydantic response schemas with proper field descriptions (these show up in Swagger, which hiring managers will look at).
- [ ] Add rate limiting using `slowapi` or a Redis-backed limiter. Different limits per endpoint.
- [ ] Add Redis caching on the hot query paths. Cache invalidation on new writes via a simple pub/sub or TTL. Document your caching strategy in the README — the reasoning matters more than the implementation.
- [ ] Add OpenAPI tags, response examples, and a proper API description. Generate a screenshot of Swagger for the README.
- [ ] Tests for every endpoint, plus a test that asserts the cache is actually used (mock Redis, check it's hit).

**Target commits (~13):** add filtering, add cursor pagination, add pagination tests, add response schemas, add rate limiter, add rate limit tests, add cache layer, add cache invalidation, add cache tests, polish OpenAPI metadata, add Swagger screenshot, update README.

**End-of-week check:** Your `/docs` endpoint looks like a real API product, not a FastAPI starter template. Someone reading the README should know how to call every endpoint within 60 seconds.

---

## Week 4 — Observability (15–20 hours)

**Goal:** You can see what the service is doing. This week is what separates "portfolio project" from "toy."

- [ ] Add Prometheus metrics: counters for events ingested by source, histograms for ingestion latency and query latency, gauges for worker state (connected/disconnected/retrying), DB connection pool usage.
- [ ] Expose `/metrics` endpoint.
- [ ] Add Grafana to docker-compose with a provisioned dashboard showing the key metrics. Commit the dashboard JSON. This is rare in junior portfolios and extremely impressive.
- [ ] Add request tracing IDs: every HTTP request gets a UUID that appears in every log line generated by that request. Every ingestion event gets a similar ID.
- [ ] Add `/debug/stats` endpoint (auth-protected) that returns worker status, cache hit rates, DB pool stats.
- [ ] Write one ADR (Architecture Decision Record) in `docs/adr/` explaining why you chose Prometheus + Grafana over alternatives. This signals senior thinking.

**Target commits (~12):** add prometheus client, add ingestion metrics, add query metrics, add worker state metrics, expose metrics endpoint, add grafana to compose, add dashboard JSON, add correlation tracing, add debug stats endpoint, add first ADR, dashboard screenshots in README.

**End-of-week check:** Run the stack for 24+ hours. Screenshot the Grafana dashboard. The screenshot should tell a story — ingestion rate varying through the day, query latency staying flat, zero errors. **This screenshot is one of the most valuable artefacts in the whole project.** Put it in the README.

---

## Week 5 — Deployment + retention (15–20 hours)

**Goal:** It runs on the public internet, forever, for free.

- [ ] Deploy to Fly.io or Railway (both have generous free tiers). You need the app, Postgres, and Redis. Fly has free Postgres; Railway's is time-limited — pick accordingly.
- [ ] Set up proper secrets management (no `.env` files in prod, use the platform's secret store).
- [ ] Configure a staging/prod split or at least proper environment separation.
- [ ] Add a retention policy: events older than N days get deleted (or downsampled into hourly aggregates in a separate table — more impressive if you have time). Implement this as a scheduled job.
- [ ] Add automated database backups or at least document the backup strategy in an ADR.
- [ ] Add a public status badge to the README: uptime, build status, latest deploy.
- [ ] Add a simple landing page at `/` that explains what the service is and links to `/docs`, `/metrics` (auth-protected), and the GitHub repo.

**Target commits (~10):** add fly.io config, add production settings, add secret management, add retention job, add retention tests, add backup ADR, add landing page, configure prod logging, add deploy workflow to CI, README update with live URL.

**End-of-week check:** Your README has a live URL at the top. Anyone can click it, see it running, hit `/docs`, and call the API. This single fact puts you in the top ~10% of self-taught developer portfolios.

---

## Week 6 — Polish + write-up (15–20 hours)

**Goal:** Make the repo tell its own story. Most of this week is writing, not coding.

- [ ] Rewrite the README from scratch now that you know what the project actually is. Structure: one-sentence pitch, live demo link, Grafana dashboard screenshot, why it exists, architecture diagram, key design decisions (link to your ADRs), how to run it locally, testing strategy, deployment.
- [ ] Add an `ARCHITECTURE.md` with a diagram (use Mermaid — renders on GitHub). Show the data flow: source → worker → Postgres → cache → API → client.
- [ ] Clean up any TODOs in the code. If it's not done by now, remove the TODO and file a GitHub issue instead.
- [ ] Write 2–3 more ADRs covering the decisions you made in earlier weeks. Backfilling ADRs is legitimate and common — they document decisions, not the process of making them.
- [ ] Write one blog post (Dev.to or Medium, or both): pick the single most interesting technical problem you solved (likely the circuit breaker or the dedup-under-load work) and write 800–1500 words about it. Link it from the repo README. Link the repo from the post.
- [ ] Final pass: check every file has a reason to exist, every test asserts something meaningful, the commit history reads like a coherent story.
- [ ] Add the project prominently to your GitHub profile README (pin it), update your CV experience section to include it, and update your LinkedIn.

**Target commits (~8, mostly docs):** rewrite README, add architecture doc, add mermaid diagram, backfill ADR 2, backfill ADR 3, clean up TODOs, add blog post link, final polish.

**End-of-week check:** Send the repo link to one person you trust — ideally another developer. Ask them: "If you were hiring a junior backend dev, would this make you want to interview this person?" Iterate on their feedback.

---

## Picking your data source

This matters more than you might think. The source gives the project personality and determines whether it's memorable.

**Good options** (ordered roughly by how distinctive they are):

- **Maritime AIS data** (ship positions). Plays off your Navy background — instant interview story. APIs: aisstream.io (free tier), or raw AIS feeds. Hugely distinctive.
- **EU ENTSO-E energy grid data** (electricity generation, prices, cross-border flows). Real-time, genuinely useful, almost nobody builds portfolio projects on it. Free API with registration.
- **Greek government open data** (data.gov.gr) — various real-time or near-real-time feeds. Local relevance, rare on GitHub.
- **GitHub firehose** (public events API) — interesting scale challenge, easy to get started.
- **Wikipedia recent changes stream** — real-time, high-volume, free, tests your backpressure handling.

**Skip these:** crypto prices (cliché), weather (cliché), Twitter/X (API is painful and expensive), any LLM-related feed.

**My vote:** AIS maritime data. The Navy connection gives you a 30-second interview opener that nobody else has. "I built a real-time ingestion service for ship tracking data — I got interested in the problem during my time as a submarine operator." That's the kind of line that makes a hiring manager remember you.

---

## Final reminders

- Save this plan somewhere. Print it if you want.
- Every Sunday night, check yourself against that week's end-of-week check.
- If you skipped something, don't move on — catch up first.
- The plan only works if each week's foundation is solid before you build on it.

When it's done, come back. We'll look at how to use it in your job search properly — which companies to target, how to frame it in applications, how to talk about it in interviews. **The project is a tool, not the endpoint.**
