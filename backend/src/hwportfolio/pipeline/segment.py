"""Segmentation: find text lines, group them into regions, detect ruled paper.

Everything returns plain bounding boxes in deskewed-image coordinates. These
boxes become Region rows (unit of transcription) and feed the observation
branch (unit of measurement). The two consumers share the geometry but nothing
else — see GOALS §5.1 on branch independence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .deskew import _ink_mask


@dataclass
class LineBox:
    x: int
    y: int
    w: int
    h: int


@dataclass
class SegmentResult:
    lines: list[LineBox] = field(default_factory=list)
    regions: list[dict] = field(default_factory=list)   # {kind, x, y, w, h}
    ruled: bool = False
    rule_ys: list[int] = field(default_factory=list)    # y of each detected rule line


def detect_ruled_lines(gray: np.ndarray) -> list[int]:
    """Detect printed horizontal rules (notebook/penmanship paper).

    Long, thin, near-full-width dark runs. Returns the y coordinate of each.
    """
    mask = _ink_mask(gray)
    width = gray.shape[1]
    horizontal = cv2.morphologyEx(
        mask, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(width // 3, 30), 1)),
    )
    row_hits = (horizontal > 0).sum(axis=1)
    candidate_rows = np.where(row_hits > width * 0.5)[0]
    if len(candidate_rows) == 0:
        return []
    # Collapse adjacent rows belonging to the same printed rule.
    rule_ys: list[int] = []
    group = [int(candidate_rows[0])]
    for y in candidate_rows[1:]:
        if y - group[-1] <= 3:
            group.append(int(y))
        else:
            rule_ys.append(int(np.mean(group)))
            group = [int(y)]
    rule_ys.append(int(np.mean(group)))
    return rule_ys


def find_text_lines(gray: np.ndarray, exclude_rule_ys: list[int] | None = None) -> list[LineBox]:
    """Text-line detection via horizontal projection of the ink mask."""
    mask = _ink_mask(gray)
    # Remove printed rules so they don't glue text lines together.
    for y in exclude_rule_ys or []:
        y0, y1 = max(0, y - 2), min(mask.shape[0], y + 3)
        mask[y0:y1, :] = 0

    profile = (mask > 0).sum(axis=1)
    height, width = mask.shape
    threshold = max(3, int(width * 0.005))
    in_line = profile > threshold

    lines: list[LineBox] = []
    start = None
    for y, active in enumerate(in_line):
        if active and start is None:
            start = y
        elif not active and start is not None:
            if y - start >= 6:  # minimum plausible glyph height
                band = mask[start:y, :]
                cols = np.where((band > 0).any(axis=0))[0]
                if len(cols) > 0:
                    lines.append(LineBox(
                        x=int(cols[0]), y=int(start),
                        w=int(cols[-1] - cols[0] + 1), h=int(y - start),
                    ))
            start = None
    if start is not None and height - start >= 6:
        band = mask[start:, :]
        cols = np.where((band > 0).any(axis=0))[0]
        if len(cols) > 0:
            lines.append(LineBox(
                x=int(cols[0]), y=int(start),
                w=int(cols[-1] - cols[0] + 1), h=int(height - start),
            ))
    return lines


def segment(gray: np.ndarray) -> SegmentResult:
    """Full segmentation pass: rules, lines, regions.

    Region grouping for the alpha is deliberately simple: contiguous text
    lines with similar spacing form one prose region; a large gap starts a
    new region. The review UI lets the teacher fix what this gets wrong —
    review is the product, not a formality.
    """
    rule_ys = detect_ruled_lines(gray)
    ruled = len(rule_ys) >= 3
    lines = find_text_lines(gray, exclude_rule_ys=rule_ys)

    regions: list[dict] = []
    if lines:
        median_h = float(np.median([ln.h for ln in lines]))
        gap_limit = median_h * 2.5
        group: list[LineBox] = [lines[0]]
        for ln in lines[1:]:
            prev = group[-1]
            if ln.y - (prev.y + prev.h) > gap_limit:
                regions.append(_group_to_region(group))
                group = [ln]
            else:
                group.append(ln)
        regions.append(_group_to_region(group))

    return SegmentResult(lines=lines, regions=regions, ruled=ruled, rule_ys=rule_ys)


def _group_to_region(group: list[LineBox]) -> dict:
    x0 = min(ln.x for ln in group)
    y0 = min(ln.y for ln in group)
    x1 = max(ln.x + ln.w for ln in group)
    y1 = max(ln.y + ln.h for ln in group)
    return {"kind": "prose", "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
