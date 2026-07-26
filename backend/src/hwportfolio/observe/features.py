"""Measurable, defensible image-space features (GOALS §5.3).

Each function returns ObservationCandidates with pixel provenance. Magnitudes
are raw measurements — interpretation (trajectory vs the student's own
baseline, never vs peers) happens in the portal, not here.

Deliberately out of scope: pen pressure, stroke order (not recoverable from a
static photo — do not fake them).
"""

from __future__ import annotations

import numpy as np

from ..pipeline.segment import LineBox
from .geometry import Glyph, estimate_xheight, extract_glyphs
from .types import ObservationCandidate

MIN_GLYPHS_PER_LINE = 4  # below this, per-line statistics are noise


def _line_bbox(line: LineBox) -> dict:
    return {"x": line.x, "y": line.y, "w": line.w, "h": line.h}


def baseline_adherence(
    gray: np.ndarray,
    lines: list[LineBox],
    rule_ys: list[int],
    ruled: bool,
) -> list[ObservationCandidate]:
    """Deviation of glyph bottoms from the writing baseline, per line.

    Ruled paper: baseline = nearest printed rule below the line's glyph mass.
    Unruled paper: baseline = least-squares fit through glyph bottoms; the
    observation is emitted but marked suppressed (GOALS open question 5 —
    report gracefully-degraded features as suppressed, not as low-confidence
    noise).
    """
    out: list[ObservationCandidate] = []
    for line in lines:
        glyphs = extract_glyphs(gray, line)
        if len(glyphs) < MIN_GLYPHS_PER_LINE:
            continue
        xheight = estimate_xheight(glyphs)
        if xheight <= 0:
            continue
        bottoms = np.array([g.bottom for g in glyphs], dtype=float)
        xs = np.array([g.center_x for g in glyphs], dtype=float)

        if ruled and rule_ys:
            # Baseline = the printed rule closest to the median glyph bottom.
            median_bottom = float(np.median(bottoms))
            baseline_y = min(rule_ys, key=lambda y: abs(y - median_bottom))
            deviations = bottoms - baseline_y
            suppressed = False
        else:
            slope, intercept = np.polyfit(xs, bottoms, 1)
            deviations = bottoms - (slope * xs + intercept)
            suppressed = True

        rms = float(np.sqrt(np.mean(deviations ** 2)))
        out.append(ObservationCandidate(
            type="baseline_adherence",
            magnitude=rms / xheight,  # normalized: deviation in x-heights
            unit="xheight_rms",
            details={"glyph_count": len(glyphs), "ruled": ruled},
            suppressed=suppressed,
            **_line_bbox(line),
        ))
    return out


def xheight_consistency(gray: np.ndarray, lines: list[LineBox]) -> list[ObservationCandidate]:
    """Coefficient of variation of body-glyph heights across the sample."""
    heights: list[float] = []
    boxes: list[LineBox] = []
    for line in lines:
        glyphs = extract_glyphs(gray, line)
        if len(glyphs) < MIN_GLYPHS_PER_LINE:
            continue
        hs = np.array(sorted(g.h for g in glyphs), dtype=float)
        q1, q3 = np.percentile(hs, [25, 75])
        heights.extend(hs[(hs >= q1) & (hs <= q3)].tolist())
        boxes.append(line)
    if len(heights) < MIN_GLYPHS_PER_LINE or not boxes:
        return []
    arr = np.array(heights)
    mean = float(arr.mean())
    if mean <= 0:
        return []
    x0 = min(b.x for b in boxes)
    y0 = min(b.y for b in boxes)
    x1 = max(b.x + b.w for b in boxes)
    y1 = max(b.y + b.h for b in boxes)
    return [ObservationCandidate(
        type="xheight_consistency",
        magnitude=float(arr.std() / mean),
        unit="cv",
        x=x0, y=y0, w=x1 - x0, h=y1 - y0,
        details={"sample_size": len(heights)},
    )]


def ascender_descender_ratio(gray: np.ndarray, lines: list[LineBox]) -> list[ObservationCandidate]:
    """Ratio of tall-glyph height to x-height, per line with enough talls."""
    out: list[ObservationCandidate] = []
    for line in lines:
        glyphs = extract_glyphs(gray, line)
        if len(glyphs) < MIN_GLYPHS_PER_LINE:
            continue
        xheight = estimate_xheight(glyphs)
        if xheight <= 0:
            continue
        talls = [g.h for g in glyphs if g.h > xheight * 1.4]
        if len(talls) < 2:
            continue
        out.append(ObservationCandidate(
            type="ascender_descender_ratio",
            magnitude=float(np.median(talls) / xheight),
            unit="ratio",
            details={"tall_glyphs": len(talls), "xheight_px": xheight},
            **_line_bbox(line),
        ))
    return out


def spacing_ratio(gray: np.ndarray, lines: list[LineBox]) -> list[ObservationCandidate]:
    """Inter-word vs inter-letter spacing ratio, per line.

    Gaps between adjacent glyphs are split into letter gaps and word gaps at
    half the x-height. A healthy sample has clearly larger word gaps; a ratio
    near 1 means words run together (or letters are spread word-wide).
    """
    out: list[ObservationCandidate] = []
    for line in lines:
        glyphs = extract_glyphs(gray, line)
        if len(glyphs) < MIN_GLYPHS_PER_LINE + 1:
            continue
        xheight = estimate_xheight(glyphs)
        if xheight <= 0:
            continue
        gaps = []
        for a, b in zip(glyphs, glyphs[1:]):
            gap = b.x - (a.x + a.w)
            if gap > 0:
                gaps.append(float(gap))
        if len(gaps) < 3:
            continue
        threshold = xheight * 0.5
        letter_gaps = [g for g in gaps if g <= threshold]
        word_gaps = [g for g in gaps if g > threshold]
        if not letter_gaps or not word_gaps:
            continue
        out.append(ObservationCandidate(
            type="spacing_ratio",
            magnitude=float(np.mean(word_gaps) / np.mean(letter_gaps)),
            unit="ratio",
            details={
                "letter_gaps": len(letter_gaps),
                "word_gaps": len(word_gaps),
                "threshold_px": threshold,
            },
            **_line_bbox(line),
        ))
    return out


def slant_consistency(gray: np.ndarray, lines: list[LineBox]) -> list[ObservationCandidate]:
    """Standard deviation of per-glyph slant angles (degrees from vertical).

    Slant is estimated from second-order image moments of glyphs tall enough
    to have a meaningful axis. Consistency, not direction, is the signal —
    a uniform right slant is a style; a scatter of slants is a motor signal.
    """
    out: list[ObservationCandidate] = []
    for line in lines:
        glyphs = extract_glyphs(gray, line)
        angles = []
        for g in glyphs:
            if g.h < 8 or g.h < g.w * 0.8:
                continue
            ys, xs = np.nonzero(g.mask)
            if len(xs) < 10:
                continue
            xs = xs.astype(float) - xs.mean()
            ys = ys.astype(float) - ys.mean()
            mu11 = float((xs * ys).sum())
            mu02 = float((ys * ys).sum())
            if mu02 == 0:
                continue
            # Shear angle of the principal axis relative to vertical.
            angles.append(float(np.degrees(np.arctan(-mu11 / mu02))))
        if len(angles) < MIN_GLYPHS_PER_LINE:
            continue
        out.append(ObservationCandidate(
            type="slant_consistency",
            magnitude=float(np.std(angles)),
            unit="deg_std",
            details={"glyphs_measured": len(angles), "mean_slant_deg": float(np.mean(angles))},
            **_line_bbox(line),
        ))
    return out


def line_drift(gray: np.ndarray, lines: list[LineBox], ruled: bool) -> list[ObservationCandidate]:
    """Slope of the written baseline on unruled paper, per line (degrees)."""
    if ruled:
        return []  # printed rules anchor the writing; drift is a no-op signal
    out: list[ObservationCandidate] = []
    for line in lines:
        glyphs = extract_glyphs(gray, line)
        if len(glyphs) < MIN_GLYPHS_PER_LINE:
            continue
        xs = np.array([g.center_x for g in glyphs], dtype=float)
        bottoms = np.array([g.bottom for g in glyphs], dtype=float)
        if xs.max() - xs.min() < 20:
            continue
        slope, _ = np.polyfit(xs, bottoms, 1)
        out.append(ObservationCandidate(
            type="line_drift",
            magnitude=abs(float(np.degrees(np.arctan(slope)))),
            unit="deg",
            details={"direction": "down" if slope > 0 else "up"},
            **_line_bbox(line),
        ))
    return out
