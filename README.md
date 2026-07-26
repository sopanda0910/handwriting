# Inkwell (alpha)

*The story of a school year, one page at a time.*

A longitudinal handwriting-and-work portfolio for K-5 classrooms. A teacher
photographs a class set of handwritten work; the system splits it per student,
produces a **verbatim** transcription (student errors preserved — they're the
signal), measures **motor/legibility features against the pixels**, and builds
a per-student timeline the teacher reviews, commits, and can share with a
parent through an expiring link.

Read [GOALS.md](GOALS.md) first — it is the product brief and the standing
constraints (§7: observational language only, no ranking, teacher-in-the-loop,
under-13 data rules). Those constraints are enforced by tests, not convention.

## Layout

```
backend/          Python: FastAPI API, OpenCV pipeline, CLI, tests
  src/hwportfolio/
    pipeline/     deskew, segmentation, QR roster matching, batch runner
    transcribe/   provider interface, verbatim prompt, mock + Claude providers
    observe/      classical-CV features + b/d/p/q reversal candidates
    jobs/         async job queue (in-process worker; see ADR 0003)
    safety/       observational-language lint (GOALS §7 C1)
frontend/         React + TS portal: roster, capture, review, timeline, share
config/skills/    versioned skill taxonomy
docs/decisions/   ADRs
```

## Quick start

Backend (Python ≥3.11):

```sh
python -m venv .venv && .venv/Scripts/pip install -e "backend[dev]"
.venv/Scripts/hwp serve            # API on http://127.0.0.1:8000
```

Frontend (Node ≥20):

```sh
cd frontend && npm install && npm run dev   # portal on http://localhost:5173
```

Everything defaults to zero-setup local mode: SQLite (`hwp.db`), local file
storage (`storage/`), the deterministic mock transcription provider, and an
in-process job worker. Environment variables (prefix `HWP_`, or a `.env`
file) switch the real pieces on:

| Variable | Default | Notes |
|---|---|---|
| `HWP_DATABASE_URL` | `sqlite:///./hwp.db` | set a `postgresql://` URL for Postgres |
| `HWP_STORAGE_DIR` | `./storage` | artifact images; only URIs go in the DB |
| `HWP_TRANSCRIPTION_PROVIDER` | `mock` | `gemini` (cheap dev/testing) or `claude` (production candidate) |
| `HWP_GEMINI_API_KEY` | — | or `GEMINI_API_KEY`; sent via `x-goog-api-key` per Google's docs |
| `HWP_GEMINI_MODEL` | `gemini-flash-latest` | stable alias — pin a model id for reproducible runs |
| `HWP_ANTHROPIC_API_KEY` | — | or a plain `ANTHROPIC_API_KEY` |
| `HWP_CLAUDE_MODEL` | `claude-opus-5` | |

All transcription providers sit behind the same interface and the same
verbatim golden-set gate — swapping provider is a config change, never a code
change (GOALS §5.2).

## Phase 0 wedge (CLI)

One photo in, verbatim text + reversal detections with bounding boxes out —
no auth, no DB, no UI:

```sh
.venv/Scripts/hwp wedge photo.png --provider claude
.venv/Scripts/hwp qr S001 "Maya R." -o maya-label.png   # printable roster label
```

The Phase 0 exit criterion (GOALS §8) needs a held-out set of ~100 real K-2
samples — synthetic pages in `backend/tests` exercise the machinery, they do
not validate the thesis. Collect real samples before trusting the wedge.

## Teacher flow

0. **Setup** — register (or pick) your school, yourself, and your classroom.
   A teacher can run multiple classrooms; roster, assignments, batches, and
   timelines are scoped to the active classroom. (No authentication yet in
   the alpha — the hierarchy is the skeleton accounts will attach to.)
1. **Roster** — add students (name + ID only, no PII), print QR header labels.
2. **Capture** — pick an assignment, upload the page photos; processing is an
   async batch job (poll status).
3. **Review** — per page: verbatim transcriptions (commit / correct /
   discard), observations with pixel provenance, unmatched pages assigned by
   hand. Nothing reaches a timeline without an explicit commit.
4. **Timelines** — the per-student record, filterable by observation type.
5. **Share** — tick specific entries, optional note (clinical language is
   rejected), generate an expiring, revocable, audit-logged parent link.

## Tests — the gates that matter

```sh
.venv/Scripts/python -m pytest backend/tests -q
```

- `test_golden_verbatim.py` — **invented-spelling preservation.** A build
  that turns `wnt` into `went` anywhere in the pipeline fails CI. Also
  asserts the verbatim prompt keeps its prohibitions. Grow
  `golden_set.py`; never shrink it.
- `test_language_lint.py` — no clinical/diagnostic language in any
  user-facing source, plus unit tests of the checker itself.
- `test_observations.py` — CV features respond directionally on synthetic
  pages; b/d/p/q shape classification; observations without a bounding box
  cannot exist.
- `test_api_flow.py` — end-to-end: upload → pipeline → QR match → review →
  commit → timeline → parent share (expiry, revocation, audit log,
  supersede-not-delete, commit-requires-student).

## Non-negotiables (from GOALS §6–§7, enforced in code)

- Every model output carries provider + model version.
- Nothing is deleted, only superseded (`supersedes_id`).
- Uncommitted work is a distinct state (`provisional`), not a flag.
- No observation without pixel provenance (bbox enforced at the model layer).
- No pathway writes to a timeline or parent view without a teacher commit.
- No cross-student comparison, ranking, or leaderboard exists in the API.
