# Building a Resilient Real-Time Ingestion Service: Circuit Breakers and Dedup Under Load

When I started `feedstream`, the project goal was simple: ingest live AIS maritime events and expose a clean query API. The real challenge was not reading a stream and writing rows. The hard part was behaving correctly when the world got messy: dropped connections, replayed messages, and retry storms.

This write-up covers the two design decisions that made the biggest difference:

1. Idempotent ingestion with a database-enforced `dedup_key`.
2. Retry with backoff plus a circuit breaker for upstream instability.

## Problem 1: Real-time streams replay data

With upstream WebSocket feeds, reconnecting is normal. So is receiving events you already saw before a disconnect. If inserts are naive, duplicates quietly accumulate and corrupt downstream analytics.

### What I chose

- Compute a deterministic `dedup_key` per event.
- Enforce uniqueness in Postgres.
- Insert with `ON CONFLICT (dedup_key) DO NOTHING`.

This made duplicate handling explicit and safe by default.

### Why database-level dedup won

I considered in-memory dedup and Redis windows. Both can work, but they add state and edge cases around restarts and key expiry. Postgres uniqueness is simpler and more reliable for this project scope. If the worker restarts, the correctness rule still holds.

### Trade-off

Every write now checks a unique index. That is acceptable here because correctness matters more than squeezing a tiny extra write throughput gain.

## Problem 2: Retries can make outages worse

During upstream instability, naive reconnect loops hammer the source and spam logs. This creates the illusion of activity without actual progress.

### What I chose

- Exponential backoff with jitter for reconnects.
- Circuit breaker to pause attempts after repeated failures.
- Graceful transition back to retry mode after cool-down.

This creates a stable failure mode: less noise, lower pressure, clearer operational signals.

### Why this pairing works

Backoff handles transient failures. The circuit breaker handles sustained failures. Together they avoid retry storms and protect both the upstream and my own service.

## What observability taught me

Adding Prometheus and Grafana changed how I debugged problems:

- Counters showed ingest success vs failure trends.
- Latency histograms exposed slow-path behavior.
- Worker state gauges made reconnect/circuit-breaker behavior visible in real time.

Without metrics, resilience logic is hard to validate. With metrics, it becomes measurable.

## Testing strategy that paid off

I added tests specifically for failure behavior:

- Duplicate event ingested twice -> one stored row.
- Source fails N times -> eventually reconnects under retry policy.
- Worker receives shutdown signal -> finishes current batch and exits cleanly.

These tests gave confidence that recovery logic was not just theoretically correct.

## What I’d improve next

- Add alerting rules for sustained open-circuit states.
- Expand dedup metrics and expose replay-rate trends on dashboards.
- Add load tests targeting cache invalidation behavior under burst writes.

## Closing

The most useful lesson from this project: resilience is a product feature, not an afterthought. In real-time systems, correctness under failure is what users actually experience.

---

If you want to explore the implementation details, see:

- Repository: `feedstream`
- Architecture: `ARCHITECTURE.md`
- ADRs: `docs/adr/0003`, `0004`, `0005`
