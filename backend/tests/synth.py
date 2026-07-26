"""Synthetic page images for tests.

Real K-2 photos belong in the Phase 0 held-out set (not in the repo); these
synthetic pages exercise the geometry and the pipeline deterministically.
"""

from __future__ import annotations

import cv2
import numpy as np

PAGE_W, PAGE_H = 1000, 1400


def blank_page() -> np.ndarray:
    return np.full((PAGE_H, PAGE_W, 3), 255, dtype=np.uint8)


def add_rules(page: np.ndarray, spacing: int = 100, start: int = 300) -> list[int]:
    ys = []
    for y in range(start, PAGE_H - 100, spacing):
        cv2.line(page, (40, y), (PAGE_W - 40, y), (170, 170, 170), 2)
        ys.append(y)
    return ys


def write_lines(
    page: np.ndarray,
    lines: list[str],
    start_y: int = 290,
    spacing: int = 100,
    x: int = 60,
    scale: float = 1.6,
    thickness: int = 3,
    drift_per_char: float = 0.0,
) -> None:
    """Draw text with per-line optional vertical drift (simulates line drift)."""
    for i, text in enumerate(lines):
        y = start_y + i * spacing
        if drift_per_char == 0.0:
            cv2.putText(page, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                        scale, (20, 20, 20), thickness, cv2.LINE_AA)
        else:
            cx = x
            cy = float(y)
            for ch in text:
                cv2.putText(page, ch, (int(cx), int(cy)), cv2.FONT_HERSHEY_SIMPLEX,
                            scale, (20, 20, 20), thickness, cv2.LINE_AA)
                (w, _), _ = cv2.getTextSize(ch, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
                cx += w + 4
                cy += drift_per_char


def draw_bowl_stem_glyph(
    page: np.ndarray, x: int, y: int, shape: str,
    stem_h: int = 60, bowl_r: int = 16, thickness: int = 5,
) -> tuple[int, int, int, int]:
    """Draw a b/d/p/q-shaped glyph. (x, y) is the top-left of the glyph box.

    Returns the glyph bounding box (x, y, w, h).
    """
    w = bowl_r * 2 + thickness
    h = stem_h
    stem_x = x + thickness // 2 if shape in ("b", "p") else x + w - thickness // 2
    cv2.line(page, (stem_x, y), (stem_x, y + h), (20, 20, 20), thickness)
    bowl_cy = y + h - bowl_r if shape in ("b", "d") else y + bowl_r
    bowl_cx = x + w - bowl_r if shape in ("b", "p") else x + bowl_r
    cv2.circle(page, (bowl_cx, bowl_cy), bowl_r, (20, 20, 20), thickness)
    return x, y, w, h


def add_qr(page: np.ndarray, payload: str, x: int = 700, y: int = 40) -> None:
    import qrcode

    qr = qrcode.QRCode(border=2, box_size=8)
    qr.add_data(payload)
    qr.make(fit=True)
    img = np.array(qr.make_image(fill_color="black", back_color="white").convert("L"))
    h, w = img.shape
    page[y:y + h, x:x + w] = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def gray(page: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(page, cv2.COLOR_BGR2GRAY)
