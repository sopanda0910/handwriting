"""Observational-language enforcement (GOALS §7 C1) — lint rule over
user-facing strings, plus unit tests of the checker itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hwportfolio.safety import find_violations
from hwportfolio.safety.language import check_text

FORBIDDEN_EXAMPLES = [
    "shows signs of dysgraphia",
    "consistent with dyslexia",
    "below-average fine motor development",
    "recommend OT screening",
    "should be evaluated by a specialist",
    "this is a red flag for a motor disorder",
    "the student is at-risk",
    "recommend an evaluation",
]

ALLOWED_EXAMPLES = [
    "b/d reversals appeared in 7 of 12 samples this month, down from 11 of 12 in October.",
    "Baseline deviation averaged 0.4 x-heights this week.",
    "Word spacing ratio improved from 1.2 to 2.1 since September.",
    "Letters formed as 'd' were flagged in 3 samples; the teacher confirmed 2.",
    "Slant varied by 14 degrees across the sample.",
]


@pytest.mark.parametrize("text", FORBIDDEN_EXAMPLES)
def test_forbidden_language_is_caught(text):
    assert find_violations(text), f"Lint failed to catch: {text!r}"
    with pytest.raises(ValueError):
        check_text(text)


@pytest.mark.parametrize("text", ALLOWED_EXAMPLES)
def test_observational_language_passes(text):
    assert find_violations(text) == [], f"Lint false-positive on: {text!r}"


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "GOALS.md").exists():
            return parent
    raise RuntimeError("Repo root not found")


# Files allowed to contain the lexicon: the lint itself, its tests, and the
# product brief that defines the rule.
ALLOWLIST_PARTS = {"language.py", "test_language_lint.py", "GOALS.md"}


def test_no_clinical_language_in_source_tree():
    root = _repo_root()
    scan_dirs = [root / "backend" / "src", root / "frontend" / "src"]
    offenders: list[str] = []
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for path in scan_dir.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css"}:
                continue
            if path.name in ALLOWLIST_PARTS or "node_modules" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for violation in find_violations(text):
                offenders.append(f"{path}: {violation.matched_text!r} ({violation.reason})")
    assert not offenders, (
        "Clinical/diagnostic language found in source (GOALS §7 C1):\n"
        + "\n".join(offenders)
    )
