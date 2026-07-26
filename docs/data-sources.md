# Data sources for Phase 0 validation

GOALS §8 exit criterion needs a held-out set of ~100 real K-2 handwriting
samples. Synthetic pages in `backend/tests` exercise the machinery only.

## IRISA IntuiScript children's handwriting database

- Project: https://www-intuidoc.irisa.fr/en/projet-intuiscript%E2%80%AF-cahier-numerique-pour-laide-a-lapprentissage-de-lecriture-a-lecole/
- Database page: https://www-intuidoc.irisa.fr/children-handwritings-database/
- Contents: ~27,000 handwritten characters (24 cursive letters), 147 anonymous
  children aged 3-7, collected across 40 pilot classes (2014-2017; became the
  Kaligo Digital Workbook).
- Access: contact Éric Anquetil (eric.anquetil@irisa.fr) — no open download.

Fit and caveats:
- Character-level, French cursive, captured on pen tablets (online stroke
  data). Useful for the reversal detector and letter-formation features;
  **not** a substitute for photographed English K-2 page-level work — the
  verbatim-transcription golden set still needs real page photos.
- Tablet capture includes pressure/stroke-order — signals we deliberately do
  NOT claim from static photos (GOALS §5.3). Do not let evaluation on this
  data smuggle those signals into the product.
- Any use must respect the dataset's license/consent terms; children's data —
  treat under the same C3 discipline as customer data (no re-hosting in this
  repo).

Other candidates to evaluate later: NIST SD19 (digits/letters, adult-heavy),
CVL children subset, EMNIST (letters, not page-level).
