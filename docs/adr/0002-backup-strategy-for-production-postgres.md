# ADR 0002: Backup Strategy for Production Postgres

- Date: 2026-06-26
- Status: Accepted

## Context

`feedstream` stores ingestion history in Postgres. Week 5 requires a backup strategy with clear recovery expectations.

## Decision

For production, we rely on managed Postgres automated backups (daily snapshots + point-in-time recovery when available on the provider plan). We also document a manual fallback export:

- `pg_dump` full logical backup for ad-hoc exports before risky schema changes.
- Keep retention policy independent from backup policy (retention controls hot data size, backups protect against accidental loss).

We target:

- RPO: up to 24 hours with daily snapshots.
- RTO: under 2 hours for snapshot restore plus app reconnect.

## Operational Notes

1. Verify automated backup status in provider dashboard weekly.
2. Before destructive maintenance, run a manual `pg_dump`.
3. Quarterly restore drill to validate backup integrity.
4. After restore, run smoke tests on `/healthz` and `/events`.

## Consequences

- Minimal operational overhead while using provider-managed durability.
- Recovery quality depends on provider backup tier and retention window.
- Manual `pg_dump` remains available as an extra guardrail for planned changes.
