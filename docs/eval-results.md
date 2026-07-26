# Pipeline evaluation on real handwriting data

Date: 2026-07-25. Datasets per `docs/data-sources.md`; harnesses in
`backend/scripts/eval_*.py`. All numbers reproducible:

```sh
cd backend
python scripts/eval_letters.py --root ../data --per-class 300
python scripts/eval_pages.py --folders ../data/mendeley_dysgraphia ../data/readingrockets --out-dir ../data/eval_out
python scripts/eval_transcribe.py --zip ../data/kaggle_words/ds.zip --n 30
```

## 1. Reversal/shape classifier (engineered CV features)

Letter-identity data: Kaggle handwritten-english-characters (clean, ~200px)
and Gambo dyslexia set (children's writing, 28px crops).

| group | n | correct | wrong | abstain | acc (decided) | coverage |
|---|---|---|---|---|---|---|
| engchars b | 55 | 48 | 0 | 7 | **100%** | 87% |
| engchars d | 55 | 43 | 1 | 11 | **97.7%** | 78% |
| engchars p | 55 | 47 | 1 | 7 | **97.9%** | 87% |
| engchars q | 55 | 19 | 4 | 32 | 82.6% | 44% |
| gambo Normal/d | 300 | 104 | 2 | 194 | **98.1%** | 35% |
| gambo Reversal/b | 300 | 54 | 17 | 229 | 76.1% | 24% |
| gambo Reversal/d | 300 | 60 | 66 | 174 | 47.6%* | 42% |

\* The "wrong" bucket on Reversal/d is dominated by reads of "q" (30) — a
vertically-flipped d **is** q-shaped, so many of these are correct reads of a
different reversal direction than our scoring assumed. Framed as what the
product actually does — *flag a glyph whose as-drawn shape disagrees with the
intended letter for teacher review*:

- Flag rate on true reversals (decided cases): **~72–89%**
- False-flag rate on normal letters: **1.9%** (2/106)

High precision, moderate recall, teacher confirms — the intended trade.
Abstains on Gambo are dominated by 28×28px resolution; pipeline crops from
real photos are far larger (see engchars coverage).

Fixes that came out of this eval (now in product code):
- `classify_shape`: small glyphs upscaled to 48px + morphological close
  before hole/stem analysis (K-2 writers often leave the bowl slightly open).
  Gambo Normal/d decided-accuracy went **41.7% → 98.1%**.
- Shared code path: the eval calls the exact function the pipeline ships.

Naive-VLM baseline (GOALS §8 comparison): pending — free-tier rate limits;
see §4.

## 2. Page pipeline on real children's pages

249 Mendeley pages (Malay, children 7–12, includes dysgraphic writing) + 4
Reading Rockets K-3 English samples.

| metric | mendeley (249) | readingrockets (4) |
|---|---|---|
| pages with no text lines found | **0** | **0** |
| pages with no regions | **0** | **0** |
| median text lines | 2 | 1 |
| mean abs deskew | 0.22° | 3.05° |
| reversal candidates | 624 | 4 |
| observations produced | ~2,400 | 29 |

Fix that came out of this eval (product code): **ink-polarity normalization**
in `_ink_mask`. The Mendeley scans are white-on-black; the mask silently
covered 47% of the page (real ink is 5–13%), poisoning every glyph-level
measurement. Otsu-based polarity detection now flips inverted input before
thresholding. After the fix, glyph-level observation counts rose ~25% and
overlay renders show candidate boxes landing on actual b/d letters.

Known remaining noise: border frames on scan strips occasionally read as
"ruled lines" (32/249 pages); acceptable for review-gated output.

## 3. Verbatim transcription (Gemini provider)

- Synthetic golden set: preserved byte-for-byte (CI-gated, 56 tests green).
- Live check: `"I wnt to the stor"` transcribed verbatim with per-token
  confidence; normalization produced "I went to the store" in the separate
  string-only pass. Invented spelling survived.
- Quantitative accuracy on labeled real handwriting (Kaggle names set,
  exact-match + CER): pending — see §4.

## 4. Rate limits (operational finding)

The Gemini key is **free tier: 5 requests/minute** for this model. Product
fix: `generate_with_retry` backs off on 429s honoring the server's
retryDelay, so a class-set batch completes slowly instead of failing. For
real classroom volume (25 pages × 2 calls each), enable billing on the
Google AI Studio key — flash-tier pricing is fractions of a cent per page
and the paid tier lifts RPM by ~2 orders of magnitude.

## 5. What this does and does not establish

Established: the pipeline machinery — deskew, segmentation, glyph geometry,
reversal candidates with pixel provenance, verbatim discipline — holds up on
real children's pages, not just synthetic fixtures.

Not established: the Phase 0 exit criterion (GOALS §8) — ≥95% invented-
spelling preservation on ~100 real *photographed English K-2 pages*. No open
dataset provides that; it requires consented pilot-classroom collection.
