# ADR-0004: Redis Cache with TTL and Write Invalidation

## Status
Accepted

## Context
`/events` is a hot read path with repeated query shapes (latest events, common filters). Direct DB reads for all requests increase latency and database load.

## Decision
Use Redis query-result caching for selected read endpoints.

- Cache key includes filters, sort, and cursor parameters.
- Set TTL to keep data fresh while reducing repeated DB reads.
- Invalidate event-related keys on successful new writes.

## Alternatives Considered
- No cache: simplest but higher DB load and slower p95 under burst traffic.
- Very long TTL only: lower load but stale data risk.
- Materialized views only: useful for aggregates, not enough for dynamic filtered queries.

## Consequences
- Pros: lower median/p95 latency, better resilience to read bursts.
- Cons: invalidation complexity and occasional stale reads within TTL window.

## Follow-ups
- Add cache hit ratio and invalidation count panels to Grafana.
- Revisit selective invalidation strategy if key cardinality grows.
