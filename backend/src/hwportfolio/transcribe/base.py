"""TranscriptionProvider interface (GOALS §5.2).

Transcription is a purchased commodity behind an interface — never couple to
one vendor. Every provider must return verbatim text with per-token confidence
and an explicit "genuinely illegible" flag, distinct from "legible but
non-standard".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass
class TokenSpan:
    text: str
    confidence: float          # 0..1
    illegible: bool = False    # genuinely unreadable, NOT merely non-standard


@dataclass
class TranscriptionResult:
    verbatim: str
    tokens: list[TokenSpan] = field(default_factory=list)
    provider: str = ""
    model_version: str = ""

    def to_token_dicts(self) -> list[dict]:
        return [
            {"text": t.text, "confidence": t.confidence, "illegible": t.illegible}
            for t in self.tokens
        ]


class TranscriptionProvider(Protocol):
    name: str
    model_version: str

    def transcribe(self, image: np.ndarray) -> TranscriptionResult:
        """Transcribe a prose region image, verbatim."""
        ...

    def normalize(self, verbatim: str) -> str:
        """Best-guess intended text, generated from the verbatim STRING only.

        Never from the image (GOALS §5.2) — normalization must not be able to
        peek at pixels and second-guess the verbatim pass.
        """
        ...


def get_provider(name: str | None = None) -> TranscriptionProvider:
    from ..config import settings

    name = name or settings.transcription_provider
    if name == "mock":
        from .mock import MockProvider

        return MockProvider()
    if name == "claude":
        from .claude import ClaudeProvider

        return ClaudeProvider()
    if name == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider()
    raise ValueError(f"Unknown transcription provider: {name!r}")
