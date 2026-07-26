"""Letter reversal candidate detection (b/d, p/q) — the highest-value single
feature for K-2 (GOALS §5.3).

Phase 0 tests the cheap option first (GOALS open question 3): engineered
features over segmented glyphs, no trained model. A glyph is a candidate when
it has the stem+bowl structure of b/d/p/q. We report the *shape class* the
strokes actually form — which way the stem faces, where the bowl sits — with
pixel provenance. Whether that shape is a reversal of the intended letter is
a judgment the teacher makes in review; the image alone cannot know intent,
and the observation branch must not consult the transcription (GOALS §5.1).
"""

from __future__ import annotations

import cv2
import numpy as np

from ..pipeline.segment import LineBox
from .geometry import Glyph, estimate_xheight, extract_glyphs
from .types import ObservationCandidate

# stem side + bowl vertical position -> letter shape
_SHAPE = {
    ("left", "bottom"): "b",
    ("right", "bottom"): "d",
    ("left", "top"): "p",
    ("right", "top"): "q",
}


def _hole_centroid(mask: np.ndarray) -> tuple[float, float] | None:
    """Centroid of the single enclosed hole (the bowl), or None."""
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return None
    holes = [
        contours[i]
        for i in range(len(contours))
        if hierarchy[0][i][3] != -1 and cv2.contourArea(contours[i]) >= 6
    ]
    if len(holes) != 1:
        return None  # zero holes: not a bowl letter; 2+: likely g/8/B — skip
    m = cv2.moments(holes[0])
    if m["m00"] == 0:
        return None
    return m["m10"] / m["m00"], m["m01"] / m["m00"]


def _stem_side(mask: np.ndarray) -> tuple[str, float] | None:
    """Which side carries a full-height vertical stem, and its coverage 0..1."""
    h, w = mask.shape
    if w < 4:
        return None
    col_cover = (mask > 0).sum(axis=0) / h  # fraction of glyph height inked per column
    third = max(1, w // 3)
    left_cover = float(col_cover[:third].max())
    right_cover = float(col_cover[-third:].max())
    if max(left_cover, right_cover) < 0.75:
        return None  # no dominant vertical stroke
    if abs(left_cover - right_cover) < 0.15:
        return None  # ambiguous (o with artifacts, a, etc.)
    return ("left", left_cover) if left_cover > right_cover else ("right", right_cover)


def classify_glyph(glyph: Glyph, xheight: float) -> ObservationCandidate | None:
    if xheight <= 0 or glyph.h < xheight * 1.25:
        return None  # bowl+stem letters are taller than the x-height body
    hole = _hole_centroid(glyph.mask)
    if hole is None:
        return None
    stem = _stem_side(glyph.mask)
    if stem is None:
        return None
    side, coverage = stem
    _, hole_y = hole
    bowl_pos = "bottom" if hole_y > glyph.h / 2 else "top"
    shape = _SHAPE[(side, bowl_pos)]
    return ObservationCandidate(
        type="reversal_candidate",
        magnitude=coverage,  # stem coverage doubles as detection confidence
        unit="confidence",
        x=glyph.x, y=glyph.y, w=glyph.w, h=glyph.h,
        details={
            "shape": shape,
            "stem_side": side,
            "bowl_position": bowl_pos,
        },
    )


def detect_reversal_candidates(
    gray: np.ndarray, lines: list[LineBox]
) -> list[ObservationCandidate]:
    out: list[ObservationCandidate] = []
    for line in lines:
        glyphs = extract_glyphs(gray, line)
        if not glyphs:
            continue
        xheight = estimate_xheight(glyphs)
        for glyph in glyphs:
            candidate = classify_glyph(glyph, xheight)
            if candidate is not None:
                out.append(candidate)
    return out
