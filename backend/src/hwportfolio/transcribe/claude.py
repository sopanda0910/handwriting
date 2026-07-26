"""Claude VLM transcription provider (prose regions).

Two separate calls, by design (GOALS §5.2):
- transcribe(): image -> verbatim, in strict verbatim mode with structured
  output (per-token confidence + illegible flag).
- normalize(): verbatim STRING -> normalized text. No image is sent — the
  normalizer must not be able to peek at pixels.

Requires HWP_ANTHROPIC_API_KEY (or ANTHROPIC_API_KEY in the environment).
"""

from __future__ import annotations

import base64
import json

import cv2
import numpy as np

from ..config import settings
from .base import TokenSpan, TranscriptionResult
from .verbatim_prompt import (
    NORMALIZE_SCHEMA,
    NORMALIZE_SYSTEM_PROMPT,
    TRANSCRIPTION_SCHEMA,
    VERBATIM_SYSTEM_PROMPT,
)


def _encode_png(image: np.ndarray) -> str:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("Failed to encode region image as PNG")
    return base64.standard_b64encode(buffer.tobytes()).decode("utf-8")


class ClaudeProvider:
    name = "claude"

    def __init__(self) -> None:
        import anthropic

        api_key = settings.anthropic_api_key
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = settings.claude_model
        self.model_version = self.model

    def transcribe(self, image: np.ndarray) -> TranscriptionResult:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            system=VERBATIM_SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": TRANSCRIPTION_SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": _encode_png(image),
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Transcribe this handwriting region verbatim, "
                                "following your rules exactly."
                            ),
                        },
                    ],
                }
            ],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Transcription request was refused by the model")
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)
        tokens = [
            TokenSpan(
                text=t["text"],
                confidence=float(t["confidence"]),
                illegible=bool(t["illegible"]),
            )
            for t in data.get("tokens", [])
        ]
        return TranscriptionResult(
            verbatim=data["verbatim"],
            tokens=tokens,
            provider=self.name,
            model_version=response.model,
        )

    def normalize(self, verbatim: str) -> str:
        if not verbatim.strip():
            return ""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=NORMALIZE_SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": NORMALIZE_SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Verbatim transcription (student errors preserved):\n\n"
                        + verbatim
                    ),
                }
            ],
        )
        if response.stop_reason == "refusal":
            return ""
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)["normalized"]
