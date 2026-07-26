"""Roster matching via printed QR headers.

Decision (see docs/decisions/0002-roster-matching.md): QR headers for v1.
Name-field OCR fails on exactly the messy K-2 handwriting we target.

Payload format: ``hwp:v1:<student_external_id>``. The generator below produces
a printable sheet of header labels; teachers staple/print them on worksheets.
Detection uses OpenCV's built-in QRCodeDetector — no native zbar dependency.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import cv2
import numpy as np

QR_PREFIX = "hwp:v1:"


@dataclass
class RosterMatch:
    external_id: str
    bbox: tuple[int, int, int, int]  # x, y, w, h of the QR code on the page


def encode_payload(external_id: str) -> str:
    return f"{QR_PREFIX}{external_id}"


def decode_payload(payload: str) -> str | None:
    if payload.startswith(QR_PREFIX):
        student_id = payload[len(QR_PREFIX):].strip()
        return student_id or None
    return None


def detect(image: np.ndarray) -> RosterMatch | None:
    """Find and decode a roster QR header on a page image.

    OpenCV's decoder is sensitive to module size, so we retry at 2x and 3x
    upscales before giving up — a page with a small printed label must still
    match. Coordinates are always reported in original-image space.
    """
    detector = cv2.QRCodeDetector()
    for scale in (1.0, 2.0, 3.0):
        candidate = image if scale == 1.0 else cv2.resize(
            image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
        )
        match = _detect_at(detector, candidate)
        if match is not None:
            x, y, w, h = match.bbox
            return RosterMatch(
                external_id=match.external_id,
                bbox=(int(x / scale), int(y / scale), int(w / scale), int(h / scale)),
            )
    return None


def _detect_at(detector: cv2.QRCodeDetector, image: np.ndarray) -> RosterMatch | None:
    try:
        ok, decoded, points, _ = detector.detectAndDecodeMulti(image)
    except cv2.error:
        ok, decoded, points = False, [], None
    if ok and points is not None:
        for payload, quad in zip(decoded, points):
            external_id = decode_payload(payload or "")
            if external_id is None:
                continue
            xs, ys = quad[:, 0], quad[:, 1]
            x, y = int(xs.min()), int(ys.min())
            return RosterMatch(
                external_id=external_id,
                bbox=(x, y, int(xs.max()) - x, int(ys.max()) - y),
            )
    # Single-code path decodes some codes the multi path misses.
    try:
        payload, quad, _ = detector.detectAndDecode(image)
    except cv2.error:
        return None
    external_id = decode_payload(payload or "")
    if external_id is None or quad is None:
        return None
    quad = np.asarray(quad).reshape(-1, 2)
    xs, ys = quad[:, 0], quad[:, 1]
    x, y = int(xs.min()), int(ys.min())
    return RosterMatch(
        external_id=external_id,
        bbox=(x, y, int(xs.max()) - x, int(ys.max()) - y),
    )


def render_qr_png(external_id: str, display_name: str, box_size: int = 8) -> bytes:
    """Render one printable header label (QR + student name) as PNG bytes."""
    import qrcode
    from PIL import Image, ImageDraw

    qr = qrcode.QRCode(border=2, box_size=box_size)
    qr.add_data(encode_payload(external_id))
    qr.make(fit=True)
    code_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    label_h = 28
    canvas = Image.new("RGB", (code_img.width + 220, max(code_img.height, label_h)), "white")
    canvas.paste(code_img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.text((code_img.width + 10, code_img.height // 2 - 6), display_name, fill="black")

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()
