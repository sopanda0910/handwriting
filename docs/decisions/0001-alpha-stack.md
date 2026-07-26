# ADR 0001 — Alpha stack choices

Date: 2026-07-25. Status: accepted.

## Context

GOALS.md §5.4 sets defaults (Python/FastAPI, OpenCV, Postgres, React+TS, real
queue) and invites argument. For the alpha we deviate in two places, both
behind interfaces so the production default remains reachable without schema
or API changes.

## Decisions

1. **SQLite by default, Postgres by env var.** The alpha must run on a
   teacher-shaped laptop with zero setup. SQLAlchemy is the only DB surface;
   `HWP_DATABASE_URL=postgresql://...` switches to Postgres unchanged. The
   JSON columns used are supported by both.
2. **Local filesystem artifact storage.** Only URIs (`local://<name>`) are
   stored in the DB per GOALS. `storage.py` is the single seam for an S3/GCS
   backend.
3. **Structured outputs for transcription.** The Claude provider uses JSON
   schema output (`output_config.format`) so per-token confidence and the
   illegible flag are machine-enforced, not parsed from prose.

## Consequences

Production deployment requires: Postgres, object storage, and the queue swap
(ADR 0003). None require touching the data model or API contracts.
