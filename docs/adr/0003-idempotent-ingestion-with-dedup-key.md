# ADR-0003: Idempotent Ingestion with `dedup_key`

## Status
Accepted

## Context
The ingestion worker can reconnect and replay upstream data. Without deduplication, duplicate events would be persisted and pollute query results.

## Decision
Use a deterministic `dedup_key` per event and enforce uniqueness at the database layer.

- Add a unique index/constraint on `events.dedup_key`.
- Insert with `ON CONFLICT (dedup_key) DO NOTHING`.
- Treat duplicate writes as expected behavior, not errors.

## Alternatives Considered
- App-level dedup only (in-memory set): fails across process restarts and deployments.
- Redis-based dedup window: adds complexity and potential key-expiry edge cases.
- Accept duplicates and dedup at query time: higher read complexity and cost.

## Consequences
- Pros: strong correctness guarantee at the source of truth, simple replay safety, robust to restarts.
- Cons: requires stable key derivation and a DB uniqueness check on every insert.

## Follow-ups
- Track dedup-hit metric to monitor replay rate.
- Validate dedup key generation for all supported AIS event shapes.
