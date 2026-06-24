# ADR-0001: Prometheus + Grafana for Observability

## Status
Accepted

## Context
Week 4 requires first-class observability for API and ingestion worker: metrics, dashboarding, traceable requests, and operational debugging.

## Decision
Use Prometheus for metrics collection and Grafana for visualization.

## Alternatives Considered
- Managed APM (Datadog/New Relic): faster setup, but recurring cost and less portfolio-portable.
- OpenTelemetry Collector stack: powerful, but heavier than needed for current scope.
- Application-only logs without metrics: insufficient for latency and throughput analysis.

## Consequences
- Pros: standard OSS stack, reproducible locally with Docker Compose, easy to demonstrate in interviews.
- Cons: extra infra services to run and maintain, manual dashboard curation required.

## Follow-ups
- Add alerting rules for sustained ingestion failures.
- Add SLO panels for p95 query latency and ingestion success ratio.
