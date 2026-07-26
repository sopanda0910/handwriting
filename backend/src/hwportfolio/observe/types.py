"""Observation branch shared types.

Every candidate carries a bounding box — an observation without pixel
provenance must not be stored (GOALS §5.3), and that is enforced again at the
model layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Version stamp for the classical-CV observation pipeline. Bump on any change
# that alters magnitudes — the timeline is worthless if it silently mixes
# measurement regimes (GOALS §6).
OBSERVE_MODEL_VERSION = "hwp-observe-0.1.0"


@dataclass
class ObservationCandidate:
    type: str          # baseline_adherence, xheight_consistency, spacing_ratio,
                       # slant_consistency, reversal_candidate, line_drift,
                       # ascender_descender_ratio
    magnitude: float
    unit: str
    x: int
    y: int
    w: int
    h: int
    details: dict = field(default_factory=dict)
    suppressed: bool = False  # e.g. baseline features on unruled paper
