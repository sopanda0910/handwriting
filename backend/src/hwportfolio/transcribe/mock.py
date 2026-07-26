"""Mock transcription provider for local dev and tests. No network.

Transcription: if the caller registered ground truth for the image (tests do
this), return it verbatim; otherwise return an empty result. The mock must
behave like a *well-behaved* provider — it never edits the text it returns —
so end-to-end tests can verify that the rest of the pipeline preserves
verbatim text byte-for-byte.

Normalization: a small rule-based invented-spelling dictionary. Good enough
for dev; the Claude provider does this properly from the verbatim string.
"""

from __future__ import annotations

import hashlib

import numpy as np

from .base import TokenSpan, TranscriptionResult

# Common K-2 invented spellings → standard forms, for the mock normalizer only.
_NORMALIZE_MAP = {
    "wnt": "went",
    "stor": "store",
    "becuz": "because",
    "cuz": "because",
    "frend": "friend",
    "sed": "said",
    "wuz": "was",
    "hous": "house",
    "skool": "school",
    "littel": "little",
    "wat": "what",
    "thay": "they",
    "hav": "have",
    "lik": "like",
    "gud": "good",
}


def image_key(image: np.ndarray) -> str:
    return hashlib.sha1(np.ascontiguousarray(image).tobytes()).hexdigest()


class MockProvider:
    name = "mock"
    model_version = "mock-1"

    # Class-level registry: image hash -> ground-truth verbatim text.
    _ground_truth: dict[str, str] = {}

    @classmethod
    def register_ground_truth(cls, image: np.ndarray, verbatim: str) -> None:
        cls._ground_truth[image_key(image)] = verbatim

    @classmethod
    def clear_ground_truth(cls) -> None:
        cls._ground_truth.clear()

    def transcribe(self, image: np.ndarray) -> TranscriptionResult:
        verbatim = self._ground_truth.get(image_key(image), "")
        tokens = [
            TokenSpan(text=tok, confidence=0.99, illegible=False)
            for tok in verbatim.split()
        ]
        return TranscriptionResult(
            verbatim=verbatim,
            tokens=tokens,
            provider=self.name,
            model_version=self.model_version,
        )

    def normalize(self, verbatim: str) -> str:
        out_words = []
        for word in verbatim.split(" "):
            stripped = word.strip(".,!?\"'")
            replacement = _NORMALIZE_MAP.get(stripped.lower())
            if replacement is not None:
                # Preserve leading/trailing punctuation around the word.
                head = word[: len(word) - len(word.lstrip(".,!?\"'"))]
                tail = word[len(word.rstrip(".,!?\"'")):]
                core = replacement.capitalize() if stripped[:1].isupper() else replacement
                out_words.append(f"{head}{core}{tail}")
            else:
                out_words.append(word)
        return " ".join(out_words)
