"""Gemini VLM transcription provider (dev/testing tier).

Identical contract and discipline as the Claude provider (GOALS §5.2):
- transcribe(): image -> verbatim, strict verbatim mode, structured JSON with
  per-token confidence + illegible flag. Same VERBATIM_SYSTEM_PROMPT — the
  golden-set gate applies to every provider equally.
- normalize(): verbatim STRING -> normalized text. No image is sent.

Requires HWP_GEMINI_API_KEY (or GEMINI_API_KEY in the environment).
"""

from __future__ import annotations

import json
import re
import time

import cv2
import numpy as np
from pydantic import BaseModel

from ..config import settings
from .base import TokenSpan, TranscriptionResult
from .verbatim_prompt import NORMALIZE_SYSTEM_PROMPT, VERBATIM_SYSTEM_PROMPT


class _Token(BaseModel):
    text: str
    confidence: float
    illegible: bool


class _Transcription(BaseModel):
    verbatim: str
    tokens: list[_Token]


class _Normalization(BaseModel):
    normalized: str


def _encode_png(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("Failed to encode region image as PNG")
    return buffer.tobytes()


MAX_RETRIES = 5


def generate_with_retry(client, **kwargs):
    """Call generate_content with backoff on 429s, metered against the daily
    budget cap (costs.py). Raises BudgetExceededError once today's estimated
    spend reaches HWP_GEMINI_DAILY_BUDGET_USD — no further billing.

    Free-tier keys also allow only a handful of requests per minute; a
    class-set batch must slow down and finish, not fail. Honors the
    retryDelay the API suggests when present.
    """
    from google.genai import errors

    from .costs import check_budget, record_usage

    check_budget()
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(**kwargs)
            if getattr(response, "usage_metadata", None) is not None:
                record_usage(response.usage_metadata)
            return response
        except errors.ClientError as exc:
            if getattr(exc, "code", None) != 429 and "429" not in str(exc):
                raise
            last_error = exc
            match = re.search(r"retry in ([0-9.]+)s", str(exc), re.IGNORECASE)
            delay = float(match.group(1)) + 1 if match else 15 * (attempt + 1)
            time.sleep(min(delay, 70))
    raise last_error  # type: ignore[misc]


class GeminiProvider:
    name = "gemini"

    def __init__(self) -> None:
        from google import genai

        api_key = settings.gemini_api_key
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()
        self.model = settings.gemini_model
        self.model_version = self.model

    def transcribe(self, image: np.ndarray) -> TranscriptionResult:
        from google.genai import types

        response = generate_with_retry(
            self.client,
            model=self.model,
            contents=[
                types.Part.from_bytes(data=_encode_png(image), mime_type="image/png"),
                "Transcribe this handwriting region verbatim, following your rules exactly.",
            ],
            config=types.GenerateContentConfig(
                system_instruction=VERBATIM_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=_Transcription,
                temperature=0.0,
                # Transcription is perception, not reasoning. Thinking tokens
                # bill as output ($7.50/M) and tripled per-page cost in
                # measurement — see docs/eval-results.md.
                thinking_config=types.ThinkingConfig(thinking_level="minimal"),
            ),
        )
        data = _Transcription.model_validate(json.loads(response.text))
        return TranscriptionResult(
            verbatim=data.verbatim,
            tokens=[
                TokenSpan(text=t.text, confidence=t.confidence, illegible=t.illegible)
                for t in data.tokens
            ],
            provider=self.name,
            model_version=getattr(response, "model_version", None) or self.model,
        )

    def normalize(self, verbatim: str) -> str:
        from google.genai import types

        if not verbatim.strip():
            return ""
        response = generate_with_retry(
            self.client,
            model=self.model,
            contents=[
                "Verbatim transcription (student errors preserved):\n\n" + verbatim,
            ],
            config=types.GenerateContentConfig(
                system_instruction=NORMALIZE_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=_Normalization,
                temperature=0.0,
                thinking_config=types.ThinkingConfig(thinking_level="minimal"),
            ),
        )
        return _Normalization.model_validate(json.loads(response.text)).normalized
