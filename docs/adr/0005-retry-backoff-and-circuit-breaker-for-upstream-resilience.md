# ADR-0005: Retry/Backoff and Circuit Breaker for Upstream Resilience

## Status
Accepted

## Context
The AIS upstream feed can fail transiently (disconnects, network instability, throttling). Immediate infinite retries can amplify failure and create noisy logs.

## Decision
Adopt layered resilience in the worker:

- Exponential backoff with jitter for reconnect attempts.
- Circuit breaker that opens after repeated failures in a time window.
- Graceful recovery path from open breaker to retry state.

## Alternatives Considered
- Tight loop reconnects: simple but can overload upstream and flood logs.
- Fixed interval retries: predictable but slower recovery in some scenarios.
- No circuit breaker: easier flow but poor behavior during sustained outages.

## Consequences
- Pros: more stable behavior during outages, controlled retry pressure, cleaner operational signal.
- Cons: additional state management and tuning thresholds over time.

## Follow-ups
- Add alerting for sustained open-breaker state.
- Tune failure window and cool-down based on production telemetry.
