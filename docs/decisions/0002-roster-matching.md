# ADR 0002 — Roster matching: QR headers for v1

Date: 2026-07-25. Status: accepted (GOALS §9 open question 1, resolved as leaned).

## Decision

Printed QR header labels, payload `hwp:v1:<student_external_id>`, detected
with OpenCV's built-in QRCodeDetector (no native zbar dependency). The API
serves a printable label per student (`GET /api/students/{id}/qr.png`) and the
CLI can render one (`hwp qr`).

## Why not name-field OCR

Name-field OCR fails on exactly the messy K-2 handwriting we target, and a
silent wrong match poisons the longitudinal record — the asset the whole
product exists to protect. QR adds a printing step but is deterministic.
Unmatched pages are surfaced in review for one-click manual assignment
(`student_match_method` records `qr` vs `manual`), which is also the fallback
when a label is missing or damaged. Name-OCR can be added later as an
unblocking convenience, never as the source of truth.
