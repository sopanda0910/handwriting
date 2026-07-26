"""Run the page pipeline (deskew -> segment -> observe) over folders of real
page images and report structural metrics, with overlay renders for eyeballing.

No DB, no transcription (that's eval_transcribe.py) — this measures whether
the geometry holds up on real children's pages.

Usage:
  python scripts/eval_pages.py --folders ../data/mendeley_dysgraphia ../data/readingrockets \
      --out-dir ../data/eval_out --overlays 20
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hwportfolio.observe.features import (  # noqa: E402
    ascender_descender_ratio,
    baseline_adherence,
    line_drift,
    slant_consistency,
    spacing_ratio,
    xheight_consistency,
)
from hwportfolio.observe.reversals import detect_reversal_candidates  # noqa: E402
from hwportfolio.pipeline.deskew import deskew  # noqa: E402
from hwportfolio.pipeline.segment import segment  # noqa: E402

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def process_page(path: Path) -> dict | None:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        return None
    result = deskew(image)
    gray = cv2.cvtColor(result.image, cv2.COLOR_BGR2GRAY)
    seg = segment(gray)

    observations = []
    observations += baseline_adherence(gray, seg.lines, seg.rule_ys, seg.ruled)
    observations += xheight_consistency(gray, seg.lines)
    observations += ascender_descender_ratio(gray, seg.lines)
    observations += spacing_ratio(gray, seg.lines)
    observations += slant_consistency(gray, seg.lines)
    observations += line_drift(gray, seg.lines, seg.ruled)
    reversals = detect_reversal_candidates(gray, seg.lines)

    return {
        "path": str(path),
        "size": [image.shape[1], image.shape[0]],
        "deskew_angle": round(result.angle_deg, 2),
        "ruled": seg.ruled,
        "text_lines": len(seg.lines),
        "regions": len(seg.regions),
        "observations": Counter(o.type for o in observations),
        "suppressed": sum(1 for o in observations if o.suppressed),
        "reversal_candidates": len(reversals),
        "_render": (result.image, seg, observations, reversals),
    }


def render_overlay(entry: dict, out_path: Path) -> None:
    image, seg, observations, reversals = entry["_render"]
    canvas = image.copy()
    for line in seg.lines:
        cv2.rectangle(canvas, (line.x, line.y), (line.x + line.w, line.y + line.h),
                      (180, 160, 60), 1)
    for region in seg.regions:
        cv2.rectangle(canvas, (region["x"], region["y"]),
                      (region["x"] + region["w"], region["y"] + region["h"]),
                      (60, 120, 30), 2)
    for candidate in reversals:
        cv2.rectangle(canvas, (candidate.x, candidate.y),
                      (candidate.x + candidate.w, candidate.y + candidate.h),
                      (30, 90, 200), 2)
        cv2.putText(canvas, candidate.details["shape"],
                    (candidate.x, max(12, candidate.y - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (30, 90, 200), 1, cv2.LINE_AA)
    for y in seg.rule_ys:
        cv2.line(canvas, (0, y), (canvas.shape[1], y), (200, 200, 240), 1)
    cv2.imwrite(str(out_path), canvas)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folders", type=Path, nargs="+", required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("../data/eval_out"))
    parser.add_argument("--overlays", type=int, default=20,
                        help="Render overlay images for the first N pages per folder")
    parser.add_argument("--limit", type=int, default=0, help="Max pages per folder (0 = all)")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    summary = {}
    for folder in args.folders:
        pages = sorted(
            p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_EXTS
        )
        if args.limit:
            pages = pages[: args.limit]
        rows = []
        rendered = 0
        for index, path in enumerate(pages):
            entry = process_page(path)
            if entry is None:
                continue
            if rendered < args.overlays:
                render_overlay(entry, args.out_dir / f"{folder.name}-{path.stem}.png")
                rendered += 1
            entry.pop("_render")
            entry["observations"] = dict(entry["observations"])
            rows.append(entry)

        if not rows:
            continue
        lines = [r["text_lines"] for r in rows]
        obs_totals = Counter()
        for r in rows:
            obs_totals.update(r["observations"])
        stats = {
            "pages": len(rows),
            "pages_with_no_lines": sum(1 for v in lines if v == 0),
            "pages_with_no_regions": sum(1 for r in rows if r["regions"] == 0),
            "median_text_lines": float(np.median(lines)),
            "ruled_pages": sum(1 for r in rows if r["ruled"]),
            "mean_abs_deskew_deg": round(float(np.mean([abs(r["deskew_angle"]) for r in rows])), 2),
            "total_reversal_candidates": sum(r["reversal_candidates"] for r in rows),
            "observation_totals": dict(obs_totals),
        }
        summary[folder.name] = {"stats": stats, "pages": rows}
        print(f"== {folder.name}")
        for key, value in stats.items():
            print(f"   {key}: {value}")

    out = args.out_dir / "pages_report.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
