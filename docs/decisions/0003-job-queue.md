# ADR 0003 — Job queue: interface now, Redis later

Date: 2026-07-25. Status: accepted.

## Context

GOALS §5.4: "a real queue from day one... do not build this as
request/response and retrofit later." A hosted Redis/RQ dependency, however,
would break the zero-setup alpha (ADR 0001).

## Decision

The architectural commitment is honored at the seams, not the transport:

- Batch processing is **async from day one**: `POST .../batches` returns
  immediately; work happens via `JobQueue.enqueue()`; clients poll batch
  status. No caller can observe whether the worker is in-process or remote.
- Job state lives in the `jobs` table (queued/running/done/failed with
  timestamps and errors), independent of the backend.
- The alpha backend is a thread-pool worker (`InProcessQueue`). A Redis-backed
  implementation drops in behind the same `enqueue()` interface, selected by
  `HWP_QUEUE_BACKEND`.

## Consequences

The retrofit GOALS warns about cannot happen at the API layer — it was never
request/response. The only later work is operational (running workers).
