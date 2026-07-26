# GOALS.md

Project brief and standing context for this repository. Read this before proposing
architecture, adding dependencies, or writing feature code.

---

## 1. What we are building

A longitudinal handwriting-and-work portfolio for K-5 classrooms (extensible to
secondary later).

A teacher photographs or scans a class set of handwritten student work. The system:

1. Splits the batch into per-student artifacts and matches them to a roster.
2. Produces a **verbatim** transcription that preserves student errors exactly.
3. Produces separate **motor/legibility observations** from the image itself.
4. Appends both to a per-student timeline that persists across the school year.
5. Surfaces that timeline as an interactive portal the teacher can open, filter,
   and show to a parent during a conference.

The durable asset is the timeline, not the grading. Grading is table stakes and is
already commoditized. The record is what compounds.

---

## 2. Product thesis

Three claims. Everything in this repo should serve at least one.

**T1 — The market is stateless; we are stateful.**
Existing tools (Gradescope, Crowdmark, CoGrader, GradingPal, GradeWithAI, Graded Pro)
treat a class set as the unit of work: grade it, sync to the LMS, discard. None owns
the per-student record over time. A teacher cannot currently answer "has Maya's letter
reversal frequency gone down since October?" without manually pulling paper. We make
that a single query.

**T2 — For K-5, the student's error is the signal, not noise.**
General vision models normalize. Asked to transcribe a first-grader's "I wnt to the
stor," they emit "I went to the store," because they are trained to produce plausible
text. That normalization is correct for high-school essay grading and catastrophic for
early-literacy assessment, where invented spelling maps onto known developmental stages
and is diagnostic of phonemic awareness. We must actively suppress normalization and
treat suppression as a first-class correctness property with its own test suite.

**T3 — Handwriting quality is an image-space problem.**
Legibility, letter formation, reversals, baseline adherence, size consistency, and word
spacing do not survive transcription to text. They must be measured against the pixels.
The grading market treats handwriting as a transport layer to be stripped; the
handwriting-instruction world has the pedagogy but no automation. We sit in the gap.

---

## 3. Non-goals

Explicit. Do not build these without a decision recorded in `/docs/decisions/`.

- **Not a diagnostic or screening tool.** Never output a condition name (dysgraphia,
  dyslexia, ADHD), a severity score framed clinically, or a referral recommendation.
  See §7.
- **Not an autograder.** We never write a grade to a gradebook without explicit
  per-item teacher confirmation. The teacher grades; we transcribe, observe, and
  organize.
- **Not an LMS.** We integrate with Google Classroom and Canvas; we do not replace them.
- **Not a student-facing app.** No student login in v1. Under-13 accounts massively
  expand COPPA surface for near-zero v1 value.
- **Not an essay-scoring engine.** No holistic 1-6 rubric scores on writing quality.
- **Not doing class-wide "lesson recommendations" in v1.** This is the most
  commoditized and least trusted output in the category. Deferred to Phase 4, and only
  as *aggregated observations with linked evidence*, never as prescriptive advice.
- **Not building our own OCR.** Transcription is a purchased commodity (see §5.2).
  Our value is what we do before and after it.

---

## 4. Users and primary jobs

**Primary: K-5 classroom teacher.** Autonomy over free/cheap tools, minimal budget
authority, extremely low tolerance for setup friction. Their jobs:

- J1. Turn a stack of paper into a digital record in under 5 minutes for 25 students.
- J2. Answer "who is struggling with what, right now" without reading all 25 again.
- J3. Walk into a parent conference with evidence instead of recollection.
- J4. Hand a mid-year record to next year's teacher.

**Secondary: parent.** Read-only, time-boxed, teacher-initiated access. Not a login;
a shareable expiring view. Parents do not get raw observation data — they get the
teacher-curated view (see §6.4).

**Tertiary: school/district admin.** Phase 5. Aggregate, de-identified. Not before
we have teacher retention.

---

## 5. Architecture

### 5.1 Pipeline

```
capture → deskew/segment → roster match → [transcribe] + [observe] → review → commit
                                              (text space)  (image space)
```

Transcription and observation are **parallel, independent branches** that never see
each other's output. Do not let the transcription inform the legibility score or vice
versa — they are separate signals and coupling them creates circular reasoning that
will show up as false confidence in the UI.

Everything is **provisional until the teacher commits.** The review step is not a
formality; it is the product. Design the DB so uncommitted extractions are a distinct
state, not a nullable flag.

### 5.2 Transcription branch

Use a commodity provider behind an interface. Do not couple to one.

- `TranscriptionProvider` interface, implementations for at least two vendors.
- Mathpix is the strongest option for any math notation and is already the engine
  under Gradescope and RM Results. Use it for math-bearing regions.
- A general VLM (Claude/Gemini/GPT) handles prose regions.
- **Critical:** every prose call must run in verbatim mode. The prompt must explicitly
  forbid spelling correction, grammar correction, capitalization normalization, and
  punctuation insertion. Output must include a per-token confidence and a flag for
  "genuinely illegible" distinct from "legible but non-standard."
- Ship a golden-set regression test of real K-2 invented spelling. A build that
  silently corrects `wnt → went` **fails CI**. This is our core differentiator and it
  will regress silently on every model upgrade if we do not gate it.

Two outputs per region, both stored:
- `verbatim` — exactly what is on the page.
- `normalized` — best-guess intended text, generated in a *separate* call from the
  verbatim string, never from the image. Used for search and for content
  understanding. Never shown as "what the student wrote."

### 5.3 Observation branch (image space)

This is the hard, novel part. Expect classical CV plus a small trained model, not a
VLM prompt. VLMs are unreliable at fine spatial measurement.

Measurable, defensible features:
- Baseline adherence (deviation of glyph bottoms from the ruled line)
- Letter height consistency (variance in x-height across the sample)
- Ascender/descender proportion
- Inter-word vs. inter-letter spacing ratio
- Slant consistency
- Letter reversal detection (b/d, p/q, s, and digit reversals) — the highest-value
  single feature for K-2
- Line drift on unruled paper

Deliberately out of scope: pen pressure and stroke order. Not recoverable from a
static photo. Do not fake them.

Every observation must carry a **bounding box** on the source image. An observation
without pixel provenance cannot be shown to a teacher and must not be stored.

### 5.4 Stack

Defaults, argue if you disagree, record the outcome:

- Backend: Python (FastAPI). The CV and ML tooling lives here.
- Image processing: OpenCV for deskew/segmentation/geometry.
- DB: Postgres. Artifacts to object storage; only URIs in Postgres.
- Frontend: React + TypeScript. The portal is the product surface — invest here.
- Jobs: a real queue from day one. A 25-page batch is a minutes-long async job.
  Do not build this as a request/response and retrofit later.

---

## 6. Data model

Sketch, not gospel. Names matter; get them right early.

- `Student` — roster identity, grade band, school year. **No PII beyond name and an
  internal ID.** No DOB, no address, no demographics.
- `Assignment` — teacher-defined; type, subject, date, optional expectations.
- `Artifact` — one physical page. Image URI, capture metadata, deskew transform.
- `Region` — a bounding box on an Artifact. The unit of transcription.
- `Extraction` — verbatim + normalized text for a Region, plus provider, model
  version, confidence, and `committed_at` (null = provisional).
- `Observation` — one image-space finding. Type, magnitude, bounding box, model
  version, `committed_at`. Never a diagnosis; see §7.
- `Skill` — a curriculum-anchored construct (e.g. `letter_formation.reversals.bd`,
  `spelling.stage.semi_phonetic`). Versioned taxonomy in `/config/skills/`.
- `SkillEvidence` — links an Observation *or* Extraction to a Skill. **This is the
  join that makes the timeline queryable.** Get it right.
- `TimelineEntry` — materialized per-student view for fast portal reads.
- `ShareGrant` — parent access. Expiring token, scoped to one student, revocable,
  audit-logged on every read.

Two non-negotiable properties:

**Every model output is versioned.** Store the model/provider version on every
Extraction and Observation. When we upgrade a model mid-year, a teacher must not see
an apparent "improvement" that is actually a model change. The timeline is worthless
if it silently mixes measurement regimes.

**Nothing is deleted, only superseded.** Teacher corrections create a new record
pointing at the old one. The correction stream is our best training signal.

---

## 7. Hard constraints — safety and compliance

These are not negotiable and not deferrable to "later."

**C1 — Observational language only.** The system describes what is on the page. It
never names a condition, never uses clinical severity language, never recommends
evaluation or referral. Correct: "b/d reversals appeared in 7 of 12 samples this
month, down from 11 of 12 in October." Forbidden: "shows signs of dysgraphia,"
"below-average fine motor development," "recommend OT screening." Enforce this with a
lint rule over user-facing strings and a review checklist, not just convention.

**C2 — Variation is not deficit.** Motor delays, physical disability, left-handedness,
recent immigration, and different prior handwriting curricula all present as "poor
handwriting." The UI must never rank students by handwriting quality, never produce a
class leaderboard, and never surface a red/failing state on a motor observation.
Show trajectory against the student's own baseline, never against peers.

**C3 — Under-13 data.** COPPA applies on top of FERPA and state student-privacy law.
We are storing photographs of identified children's schoolwork. Consequences for the
build: data minimization by default, per-district retention windows with hard
deletion, no training on customer data without separate written agreement, regional
processing, full audit log on every parent-share read. Get counsel before the first
paid district — this section is engineering scaffolding, not legal advice.

**C4 — Teacher-in-the-loop is structural.** No pathway exists in the code that writes
a grade or publishes a parent-visible observation without an explicit teacher commit.
If you find yourself adding an "auto-approve" setting, stop and raise it.

---

## 8. Build phases

**Phase 0 — Prove the wedge (do this first, before any product surface).**
A CLI that takes one photo of real K-2 handwriting and emits verbatim text plus
reversal detections with bounding boxes. No auth, no DB, no UI.
*Exit criterion:* on a held-out set of 100 real K-2 samples, verbatim transcription
preserves invented spelling ≥95% of the time, and b/d reversal detection beats a
naive VLM prompt by a margin we can state numerically. **If this fails, the thesis is
wrong and the rest of the roadmap does not matter.** Do not proceed on optimism.

**Phase 1 — Capture and review.**
Batch capture, deskew, segmentation, roster matching, the review UI. Teacher can turn
a stack into committed records. No timeline yet. Ships to ~5 friendly classrooms.
*Exit criterion:* J1 met — 25 students in under 5 minutes, measured, not estimated.

**Phase 2 — The timeline.**
Skill taxonomy, SkillEvidence, per-student portal, trajectory views. This is the moat.
*Exit criterion:* a teacher answers J2 without opening a single original artifact.

**Phase 3 — The parent view.**
ShareGrant, curated conference view, PDF export. Teacher selects what is shared;
default is share-nothing.
*Exit criterion:* used unprompted in a real conference.

**Phase 4 — Class aggregation.**
Only now. Aggregated observations with linked evidence. Descriptive, not prescriptive.

**Phase 5 — Secondary grades, LMS write-back, admin.**

---

## 9. Open questions

Resolve deliberately; record in `/docs/decisions/`.

1. **Roster matching.** Printed QR headers (reliable, adds a printing step) vs. name-
   field OCR (frictionless, fails on exactly the messy K-2 handwriting we target).
   Leaning: QR for v1, name-OCR as an unblocking convenience later.
2. **Skill taxonomy source.** Common Core alignment, a handwriting-curriculum
   taxonomy, or our own? Own taxonomy risks being unsellable to districts; CCSS
   has poor coverage of motor skills.
3. **Reversal detector.** Train our own on a labeled set, or engineer features on top
   of segmented glyphs? Phase 0 should test the cheap option first.
4. **On-device vs. cloud inference.** On-device is a strong privacy story for district
   sales and expensive to build. Probably not v1, but do not architect it out.
5. **Unruled paper.** A large fraction of K-5 work has no baseline. Several key
   features degrade badly. Detect and gracefully suppress affected observations rather
   than reporting low-confidence noise.
6. **Do we ever transcribe drawings?** K-5 work is heavily illustrated. Probably
   store, do not interpret.

---

## 10. Success criteria

Ordered by what actually predicts survival.

1. Week-8 teacher retention. A stateless tool is used at grading time and forgotten;
   ours should be opened between assignments. **If teachers only open it on grading
   day, we have built a commodity grader and the thesis has failed.**
2. Median batch time for a 25-student class set.
3. Teacher correction rate on verbatim transcription, tracked separately for K-2 and
   3-5. Rising correction rate after a model upgrade is a P0 incident.
4. Parent-share activation per teacher per term.
5. Invented-spelling preservation rate on the golden set. Never regresses.

Explicitly **not** a success metric: number of assignments auto-graded.

---

## 11. Working agreements

- Prefer boring, inspectable technology. This is an evidence system; a teacher must be
  able to trace any claim back to a rectangle on a photograph.
- No feature ships without pixel provenance.
- Model versions are recorded everywhere, always.
- When a change touches §7, stop and raise it rather than implementing.
- Every vendor accuracy claim in this space is self-reported marketing. Ours will be
  too unless we measure on held-out real classroom data. Measure.
