# feedstream

A production-grade real-time AIS maritime data pipeline: ingest, store, query, cache, and observe.

[![CI](https://github.com/Archangel-77/feedstream/actions/workflows/ci.yml/badge.svg)](https://github.com/Archangel-77/feedstream/actions/workflows/ci.yml)
[![Deploy](https://github.com/Archangel-77/feedstream/actions/workflows/deploy.yml/badge.svg)](https://github.com/Archangel-77/feedstream/actions/workflows/deploy.yml)
[![Uptime](https://img.shields.io/website?url=https%3A%2F%2Ffeedstream.fly.dev%2Fhealthz&label=uptime)](https://feedstream.fly.dev)

**Live Demo**: [https://feedstream.fly.dev](https://feedstream.fly.dev)  \n**API Docs**: [https://feedstream.fly.dev/docs](https://feedstream.fly.dev/docs)  \n**Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## 🎯 What This Is

`feedstream` is a **backend portfolio project** built to demonstrate real-world engineering excellence — not just code that works, but systems that are **observable, resilient, operable, and hire-worthy**.

It ingests live AIS (Automatic Identification System) ship-tracking data from [aisstream.io](https://aisstream.io), stores it durably in PostgreSQL, exposes a clean, filtered, paginated API via FastAPI, and layers in caching, observability, retention, and deployment best practices — all with production-grade tooling and documentation.

> 💡 *Built by someone who worked with maritime systems — this isn’t a toy. It’s a signal of engineering maturity.*

---

## ✨ Why This Stands Out

Most backend projects show CRUD APIs. This one shows **how to build systems that survive reality**.

| Feature | Why It Matters |
|-------|----------------|
| **Idempotent Ingestion** | Uses `dedup_key` + `ON CONFLICT DO NOTHING` to guarantee no duplicate ship events — even during network flapping or replays. |
| **Resilient Worker** | Exponential backoff with jitter + circuit breaker prevents retry storms and protects upstream services. |
| **Observable by Design** | Prometheus metrics (ingest rate, latency, worker state), Grafana dashboards, request tracing (`X-Request-ID`), and `/debug/stats` endpoint. |
| **Performant API** | Cursor-based pagination (no offset limits), Redis caching with TTL + write invalidation, filtering by ship type, time, region. |
| **Production-Ready** | Docker Compose for local dev, deployed on Fly.io, secrets managed via platform, CI/CD with lint/test/deploy, data retention policy. |
| **Thoughtfully Documented** | Architecture decision records (ADRs), clear diagrams, testing strategy, and operational notes. |

---

## 🏗️ Architecture at a Glance
