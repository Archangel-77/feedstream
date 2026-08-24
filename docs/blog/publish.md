# Publishing checklist — "Building a Resilient Real-Time Ingestion Service"

The article draft lives in [`circuit-breaker-dedup-lessons.md`](circuit-breaker-dedup-lessons.md).

## Front matter (Dev.to / Medium)

Use this as the Dev.to front matter, or as the title/subtitle for Medium.

```yaml
---
title: Building a Resilient Real-Time Ingestion Service
subtitle: Circuit breakers and idempotent writes under load
published: false
description: >-
  Lessons from building feedstream — a real-time AIS ingestion service.
  Why database-level dedup won, and how retry with backoff plus a circuit
  breaker keep the worker stable when the upstream gets messy.
tags:
  - python
  - backend
  - architecture
  - fastapi
  - observability
cover_image: https://feedstream.fly.dev/ # replace with a real hero image URL
canonical_url: https://feedstream.fly.dev # replace after publishing
---
```

## Steps

1. Copy the body from `circuit-breaker-dedup-lessons.md` into the editor.
2. Add a hero image (a Grafana dashboard screenshot or the repo's README diagram).
3. Make sure the body links point to:
   - Repo: `https://github.com/Archangel-77/feedstream`
   - `ARCHITECTURE.md`
   - ADRs `docs/adr/0003`, `docs/adr/0004`, `docs/adr/0005`
4. Publish, then update the live URL in `README.md` and `docs/career/week6-rollout-checklist.md`.
5. Add the repository link inside the published article ("Read more / source").
