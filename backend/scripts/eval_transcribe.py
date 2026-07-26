"""Transcription accuracy of the Gemini provider on labeled handwriting.

Uses the Kaggle handwritten-names dataset (413k word images with ground-truth
labels). Samples images directly out of the zip. Reports exact-match rate and
character error rate (CER). Names are written in capitals; comparison is
case-insensitive so we measure reading accuracy, not case style.

Usage:
  python scripts/eval_transcribe.py --zip ../data/kaggle_words/ds.zip --n 80
"""

from __future__ import annotations

import argparse
import csv
import io
import random
import sys
import zipfile
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eval_letters import load_gemini_key  # noqa: E402  (same scripts dir)


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, default=Path("../data/kaggle_words/ds.zip"))
    parser.add_argument("--n", type=int, default=80)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--throttle", type=float, default=0.5,
                        help="Seconds between calls (13+ for free tier)")
    args = parser.parse_args()

    import os

    key = load_gemini_key()
    if not key:
        print("No Gemini key", file=sys.stderr)
        return 1
    os.environ["HWP_GEMINI_API_KEY"] = key
    os.environ.setdefault("GEMINI_API_KEY", key)

    from hwportfolio.transcribe.gemini import GeminiProvider

    archive = zipfile.ZipFile(args.zip)
    with archive.open("written_name_validation_v2.csv") as fh:
        rows = list(csv.DictReader(io.TextIOWrapper(fh, "utf-8")))
    rows = [r for r in rows if r["IDENTITY"] and r["IDENTITY"] != "UNREADABLE"]
    sample = random.Random(args.seed).sample(rows, min(args.n, len(rows)))

    import time

    provider = GeminiProvider()
    exact = 0
    total_edit = 0
    total_chars = 0
    failures: list[tuple[str, str]] = []
    for row in sample:
        time.sleep(args.throttle)
        member = f"validation_v2/validation/{row['FILENAME']}"
        data = archive.read(member)
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            continue
        try:
            result = provider.transcribe(image)
        except Exception as exc:
            print("provider error:", exc, file=sys.stderr)
            continue
        truth = row["IDENTITY"].strip().upper()
        got = result.verbatim.strip().upper()
        distance = levenshtein(got, truth)
        total_edit += distance
        total_chars += len(truth)
        if got == truth:
            exact += 1
        elif len(failures) < 12:
            failures.append((truth, got))

    n = len(sample)
    print(f"n={n}  exact-match={exact}/{n} ({exact/n:.1%})  "
          f"CER={total_edit/total_chars:.1%}")
    if failures:
        print("sample mismatches (truth -> got):")
        for truth, got in failures:
            print(f"  {truth!r} -> {got!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
