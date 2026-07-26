# Data sources for Phase 0 validation

GOALS §8 exit criterion needs a held-out set of ~100 real K-2 handwriting
samples. Synthetic pages in `backend/tests` exercise the machinery only.

## IRISA IntuiScript children's handwriting database

- Project: https://www-intuidoc.irisa.fr/en/projet-intuiscript%E2%80%AF-cahier-numerique-pour-laide-a-lapprentissage-de-lecriture-a-lecole/
- Database page: https://www-intuidoc.irisa.fr/children-handwritings-database/
- Contents: ~27,000 handwritten characters (24 cursive letters), 147 anonymous
  children aged 3-7, collected across 40 pilot classes (2014-2017; became the
  Kaligo Digital Workbook).
- Access: **direct download** from the database page (`Data_IGS.zip`), free
  for research purposes with attribution (BibTeX on the page — INSA Rennes,
  UMR IRISA). Downloaded 2026-07-25 to `data/intuiscript/` (git-ignored; we
  do not re-host children's data in the repo).

What the download actually contains (inspected):
- One CSV, 6,117 rows. **Per-character features only — no images, no stroke
  trajectories.** Columns: repeat count, letter class, anonymous student ID,
  gender, age, laterality (handedness), duration, stroke count, average and
  variance of pen pressure, and a global quality score.

Fit and caveats (revised after inspection):
- Cannot feed the reversal detector, segmentation, or the transcription
  golden set — those need pixels, and this has none.
- Still useful as **reference statistics**: per-letter difficulty priors
  (which cursive letters score lowest for 3-7 year-olds), and the laterality
  field is directly relevant to GOALS §7 C2 (left-handedness presents as
  "poor handwriting" — variation, not deficit).
- Tablet-only signals (pressure, duration, stroke count) are things we
  deliberately do NOT claim from static photos (GOALS §5.3). Do not let
  benchmarks against this data smuggle those signals into the product.
- The Phase 0 held-out set of ~100 real photographed K-2 pages is still
  unmet by this dataset.

Other candidates to evaluate later: NIST SD19 (digits/letters, adult-heavy),
CVL children subset, EMNIST (letters, not page-level).
