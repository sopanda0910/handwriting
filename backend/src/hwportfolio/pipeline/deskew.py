"""Deskew: estimate page rotation from ink geometry and correct it.

Classical CV on purpose (GOALS §11: boring, inspectable). The estimated angle
and the applied transform are returned so they can be stored on the Artifact —
every observation bbox is in deskewed-image coordinates, and the stored
transform is what maps them back to the original photo if ever needed.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

MAX_CORRECTION_DEG = 15.0  # beyond this we assume the page is intentionally rotated


@dataclass
class DeskewResult:
    image: np.ndarray
    angle_deg: float          # rotation that was applied (counter-clockwise)
    transform: dict           # serializable record for Artifact.deskew_transform


def _ink_mask(gray: np.ndarray) -> np.ndarray:
    # Adaptive threshold copes with uneven classroom-photo lighting.
    mask = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15
    )
    # Drop speckle noise.
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return mask


def estimate_skew_deg(gray: np.ndarray) -> float:
    """Estimate text skew via Hough lines over a dilated ink mask.

    Dilating horizontally merges letters into line-shaped blobs whose long
    edges track the writing baseline.
    """
    mask = _ink_mask(gray)
    merged = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1)))
    lines = cv2.HoughLinesP(
        merged, 1, np.pi / 360, threshold=80,
        minLineLength=gray.shape[1] // 4, maxLineGap=20,
    )
    if lines is None:
        return 0.0
    angles = []
    for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
        if x2 == x1:
            continue
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) <= MAX_CORRECTION_DEG:
            angles.append(angle)
    if not angles:
        return 0.0
    return float(np.median(angles))


def deskew(image: np.ndarray) -> DeskewResult:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    angle = estimate_skew_deg(gray)
    if abs(angle) < 0.1:
        return DeskewResult(image=image, angle_deg=0.0,
                            transform={"type": "rotation", "angle_deg": 0.0})
    h, w = image.shape[:2]
    center = (w / 2, h / 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image, matrix, (w, h),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
    )
    return DeskewResult(
        image=rotated,
        angle_deg=angle,
        transform={"type": "rotation", "angle_deg": angle, "center": [w / 2, h / 2]},
    )
