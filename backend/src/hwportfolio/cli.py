"""hwp — command-line interface.

`hwp wedge` is Phase 0 (GOALS §8): one photo of real K-2 handwriting in,
verbatim text plus reversal detections with bounding boxes out. No auth, no
DB, no UI. If this doesn't prove out on real samples, the rest of the roadmap
doesn't matter.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_wedge(args: argparse.Namespace) -> int:
    import cv2

    from .observe.reversals import detect_reversal_candidates
    from .pipeline.deskew import deskew
    from .pipeline.segment import segment
    from .transcribe import get_provider

    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image is None:
        print(f"error: could not read image {args.image}", file=sys.stderr)
        return 2

    result = deskew(image)
    gray = cv2.cvtColor(result.image, cv2.COLOR_BGR2GRAY)
    seg = segment(gray)

    provider = get_provider(args.provider)
    transcriptions = []
    for region in seg.regions:
        x, y, w, h = region["x"], region["y"], region["w"], region["h"]
        crop = result.image[y:y + h, x:x + w]
        t = provider.transcribe(crop)
        transcriptions.append({
            "region": {"x": x, "y": y, "w": w, "h": h},
            "verbatim": t.verbatim,
            "tokens": t.to_token_dicts(),
            "provider": t.provider,
            "model_version": t.model_version,
        })

    reversals = [
        {
            "shape": c.details["shape"],
            "stem_side": c.details["stem_side"],
            "bowl_position": c.details["bowl_position"],
            "confidence": round(c.magnitude, 3),
            "bbox": {"x": c.x, "y": c.y, "w": c.w, "h": c.h},
        }
        for c in detect_reversal_candidates(gray, seg.lines)
    ]

    output = {
        "image": str(args.image),
        "deskew_angle_deg": round(result.angle_deg, 2),
        "ruled_paper": seg.ruled,
        "text_lines": len(seg.lines),
        "transcriptions": transcriptions,
        "reversal_candidates": reversals,
    }
    print(json.dumps(output, indent=2))
    return 0


def cmd_qr(args: argparse.Namespace) -> int:
    from .pipeline.roster import render_qr_png

    png = render_qr_png(args.external_id, args.name)
    out = Path(args.output)
    out.write_bytes(png)
    print(f"Wrote {out}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("hwportfolio.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hwp", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_wedge = sub.add_parser("wedge", help="Phase 0: photo -> verbatim + reversal detections")
    p_wedge.add_argument("image", type=Path)
    p_wedge.add_argument("--provider", choices=["mock", "claude", "gemini"], default=None,
                         help="Transcription provider (default: HWP_TRANSCRIPTION_PROVIDER)")
    p_wedge.set_defaults(func=cmd_wedge)

    p_qr = sub.add_parser("qr", help="Render a printable roster QR header label")
    p_qr.add_argument("external_id")
    p_qr.add_argument("name")
    p_qr.add_argument("-o", "--output", default="qr.png")
    p_qr.set_defaults(func=cmd_qr)

    p_serve = sub.add_parser("serve", help="Run the API server")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
