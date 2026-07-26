"""Glyph extraction shared by the observation features.

A "glyph" here is a connected component of ink within a text line — an
approximation of a letter. Cursive joins letters and dots detach from i/j, so
downstream features must be robust to noisy glyph boundaries. That is fine for
the alpha: every feature is a statistic over many glyphs, not a claim about
one letter (except reversal candidates, which carry their own bbox for the
teacher to judge).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ..pipeline.deskew import _ink_mask
from ..pipeline.segment import LineBox


@dataclass
class Glyph:
    x: int
    y: int
    w: int
    h: int
    area: int
    mask: np.ndarray  # binary crop of the glyph, shape (h, w)

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def center_x(self) -> float:
        return self.x + self.w / 2


def extract_glyphs(gray: np.ndarray, line: LineBox, min_area: int = 12) -> list[Glyph]:
    """Connected components of ink inside one text line, left to right."""
    pad = max(2, line.h // 4)
    y0 = max(0, line.y - pad)
    y1 = min(gray.shape[0], line.y + line.h + pad)
    x0 = max(0, line.x)
    x1 = min(gray.shape[1], line.x + line.w)
    strip = gray[y0:y1, x0:x1]
    if strip.size == 0:
        return []

    mask = _ink_mask(strip)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    glyphs: list[Glyph] = []
    for i in range(1, count):
        gx, gy, gw, gh, area = stats[i]
        if area < min_area:
            continue
        glyph_mask = (labels[gy:gy + gh, gx:gx + gw] == i).astype(np.uint8) * 255
        glyphs.append(Glyph(
            x=int(x0 + gx), y=int(y0 + gy), w=int(gw), h=int(gh),
            area=int(area), mask=glyph_mask,
        ))
    glyphs.sort(key=lambda g: g.x)
    return glyphs


def estimate_xheight(glyphs: list[Glyph]) -> float:
    """Median height of body-sized glyphs (ascenders/descenders excluded).

    Uses the interquartile band of glyph heights so tall (b, d, k) and deep
    (p, q, g) letters don't skew the estimate.
    """
    if not glyphs:
        return 0.0
    heights = np.array(sorted(g.h for g in glyphs), dtype=float)
    q1, q3 = np.percentile(heights, [25, 75])
    body = heights[(heights >= q1) & (heights <= q3)]
    return float(np.median(body)) if len(body) else float(np.median(heights))
