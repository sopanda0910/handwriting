"""Observational-language lint (GOALS §7 C1) — enforced in code, not convention.

The system describes what is on the page. It never names a condition, never
uses clinical severity language, never recommends evaluation or referral.

Used two ways:
1. A CI test scans every user-facing string in the repo (backend messages,
   frontend source) for this lexicon.
2. The API rejects teacher-authored parent-share notes containing it — those
   notes render under our product's name in front of a parent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Case-insensitive. Word-ish patterns so "diagnose" also catches "diagnosed".
FORBIDDEN_PATTERNS: dict[str, str] = {
    r"dysgraphia": "condition name",
    r"dyslexia|dyslexic": "condition name",
    r"adhd|attention.deficit": "condition name",
    r"autis(m|tic)": "condition name",
    r"disorder": "clinical severity language",
    r"diagnos\w*": "clinical framing",
    r"impair(ed|ment)": "clinical severity language",
    r"deficit": "clinical severity language",
    r"delay(ed)?\s+(fine\s+)?motor": "clinical severity language",
    r"below[\s-]average": "peer-relative framing",
    r"behind\s+(his|her|their)\s+peers": "peer-relative framing",
    r"(occupational|physical)\s+therap\w*": "referral recommendation",
    r"\bOT\s+(screen|referral|eval)\w*": "referral recommendation",
    r"recommend\w*\s+(an?\s+)?(evaluation|screening|assessment|referral)": "referral recommendation",
    r"should\s+be\s+(evaluated|screened|assessed|tested)": "referral recommendation",
    r"red\s+flag": "clinical severity language",
    r"at[\s-]risk": "clinical severity language",
}

_COMPILED = [(re.compile(p, re.IGNORECASE), reason) for p, reason in FORBIDDEN_PATTERNS.items()]


@dataclass
class Violation:
    pattern: str
    reason: str
    matched_text: str


def find_violations(text: str) -> list[Violation]:
    violations = []
    for regex, reason in _COMPILED:
        match = regex.search(text)
        if match:
            violations.append(Violation(
                pattern=regex.pattern, reason=reason, matched_text=match.group(0)
            ))
    return violations


def check_text(text: str) -> None:
    """Raise ValueError if text violates the observational-language constraint."""
    violations = find_violations(text)
    if violations:
        details = "; ".join(f"{v.matched_text!r} ({v.reason})" for v in violations)
        raise ValueError(
            "Text violates the observational-language constraint (GOALS §7 C1): "
            + details
        )
