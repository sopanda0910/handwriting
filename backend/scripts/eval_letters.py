"""Evaluate the b/d/p/q shape classifier on labeled real-handwriting letters.

Datasets (see docs/data-sources.md):
- Gambo (Kaggle dyslexia set): letter crops labeled Normal/Reversal with a
  letter prefix. A "Reversal" image of letter X is X written mirrored, so the
  as-written shape is mirror(X): Reversal/b should read as shape 'd',
  Reversal/d as shape 'b'. Normal/d should read as shape 'd'.
- Kaggle handwritten-english-characters: letter crops labeled by identity
  (shape 'b' image should classify as 'b', etc.).

Also supports --gemini N: the naive-VLM baseline GOALS §8 asks us to beat —
ask Gemini which of b/d/p/q the crop looks like, on the same samples.

Usage:
  python scripts/eval_letters.py --root ../data --per-class 200 [--gemini 50]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hwportfolio.observe.reversals import classify_shape  # noqa: E402

MIRROR = {"b": "d", "d": "b", "p": "q", "q": "p"}


def load_glyph_mask(path: Path) -> np.ndarray | None:
    """Load a letter crop and return a clean binary mask of the largest ink blob."""
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    # Normalize polarity: ink should be the minority bright class in the mask.
    _, mask = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if (mask > 0).mean() > 0.5:
        mask = cv2.bitwise_not(mask)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count < 2:
        return None
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, area = stats[biggest]
    if area < 20 or w < 3 or h < 6:
        return None
    return (labels[y:y + h, x:x + w] == biggest).astype(np.uint8) * 255


def classify_mask(mask: np.ndarray) -> str | None:
    result = classify_shape(mask)
    return result[0] if result is not None else None


def collect_samples(root: Path, per_class: int, seed: int = 7):
    """Yield (path, expected_shape, source) for every evaluable sample."""
    rng = random.Random(seed)
    groups: list[tuple[str, list[Path], str]] = []

    gambo = root / "kaggle_dyslexia/extracted/Gambo/Train"
    if gambo.exists():
        for cls, prefix in [("Normal", "d"), ("Reversal", "b"), ("Reversal", "d")]:
            # Windows globbing is case-insensitive; filter to the exact
            # lowercase prefix so uppercase D/B images don't sneak in.
            paths = sorted(
                p for p in (gambo / cls).glob(f"{prefix}[-_]*.png")
                if p.name[0] == prefix
            )
            expected = prefix if cls == "Normal" else MIRROR[prefix]
            groups.append((f"gambo:{cls}/{prefix}", paths, expected))

    engchars = root / "kaggle_engchars/handwritten-english-characters-and-digits/combined_folder"
    if engchars.exists():
        for letter in "bdpq":
            paths = sorted((engchars / "train" / letter).glob("*.png")) + sorted(
                (engchars / "test" / letter).glob("*.png")
            )
            if paths:
                groups.append((f"engchars:{letter}", paths, letter))

    for name, paths, expected in groups:
        if not paths:
            continue
        sample = rng.sample(paths, min(per_class, len(paths)))
        for path in sample:
            yield path, expected, name


def load_gemini_key() -> str | None:
    """Key from env or the repo-root .env (scripts run from backend/)."""
    import os

    key = os.environ.get("HWP_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    for parent in Path(__file__).resolve().parents:
        env_file = parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("HWP_GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return None


def gemini_shape(client, path: Path, model: str) -> str | None:
    """Returns 'b'/'d'/'p'/'q', None for a non-answer, or raises on API failure."""
    from google.genai import types

    from hwportfolio.transcribe.gemini import generate_with_retry

    data = path.read_bytes()
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    response = generate_with_retry(
        client,
        model=model,
        contents=[
            types.Part.from_bytes(data=data, mime_type=mime),
            "This is one handwritten letter. As drawn on the page, which of "
            "b, d, p, q does the shape most resemble? Answer with the single "
            "letter only, or 'none' if it is not one of those shapes.",
        ],
        config=types.GenerateContentConfig(
            temperature=0.0,
            thinking_config=types.ThinkingConfig(thinking_level="minimal"),
        ),
    )
    answer = (response.text or "").strip().lower()[:4]
    return answer[0] if answer[:1] in "bdpq" else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("../data"))
    parser.add_argument("--per-class", type=int, default=200)
    parser.add_argument("--gemini", type=int, default=0,
                        help="Also run the naive Gemini baseline on N samples per group")
    parser.add_argument("--throttle", type=float, default=13.0,
                        help="Seconds between Gemini calls (free tier: 5/min)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    results = defaultdict(lambda: Counter())
    per_group_paths: dict[str, list[tuple[Path, str]]] = defaultdict(list)

    for path, expected, group in collect_samples(args.root, args.per_class):
        per_group_paths[group].append((path, expected))
        mask = load_glyph_mask(path)
        predicted = classify_mask(mask) if mask is not None else None
        key = "correct" if predicted == expected else ("abstain" if predicted is None else "wrong")
        results[group][key] += 1
        results[group][f"pred_{predicted}"] += 1

    report = {"cv": {}, "gemini": {}}
    print(f"{'group':28s} {'n':>5} {'correct':>8} {'wrong':>6} {'abstain':>8} {'acc(decided)':>13}")
    for group, counts in sorted(results.items()):
        n = counts["correct"] + counts["wrong"] + counts["abstain"]
        decided = counts["correct"] + counts["wrong"]
        acc = counts["correct"] / decided if decided else 0.0
        print(f"{group:28s} {n:>5} {counts['correct']:>8} {counts['wrong']:>6} "
              f"{counts['abstain']:>8} {acc:>12.1%}")
        report["cv"][group] = {
            "n": n, "correct": counts["correct"], "wrong": counts["wrong"],
            "abstain": counts["abstain"], "accuracy_decided": round(acc, 4),
            "coverage": round(decided / n, 4) if n else 0.0,
        }

    if args.gemini > 0:
        from google import genai

        key = load_gemini_key()
        if not key:
            print("No Gemini key found; skipping baseline", file=sys.stderr)
            return 1
        client = genai.Client(api_key=key)
        model = "gemini-flash-latest"
        print(f"\nGemini baseline ({model}):")
        rng = random.Random(11)
        import time

        for group, pairs in sorted(per_group_paths.items()):
            subset = rng.sample(pairs, min(args.gemini, len(pairs)))
            hits = misses = abstains = errors = 0
            for path, expected in subset:
                time.sleep(args.throttle)  # free tier: 5 requests/minute
                try:
                    answer = gemini_shape(client, path, model)
                except Exception as exc:
                    errors += 1
                    print(f"  api error on {path.name}: {str(exc)[:80]}", file=sys.stderr)
                    continue
                if answer is None:
                    abstains += 1
                elif answer == expected:
                    hits += 1
                else:
                    misses += 1
            decided = hits + misses
            acc = hits / decided if decided else 0.0
            print(f"{group:28s} n={len(subset):<4} correct={hits:<4} wrong={misses:<4} "
                  f"abstain={abstains:<4} acc(decided)={acc:.1%}")
            report["gemini"][group] = {
                "n": len(subset), "correct": hits, "wrong": misses,
                "abstain": abstains, "accuracy_decided": round(acc, 4),
            }

    if args.out:
        args.out.write_text(json.dumps(report, indent=2))
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
