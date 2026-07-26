"""CI gate: invented-spelling preservation (GOALS §5.2, §10.5 — never regresses).

Three layers:
1. The verbatim prompt must contain every required prohibition.
2. End-to-end through the real pipeline (deskew -> segment -> transcribe ->
   store), the stored verbatim must equal what the provider read off the page
   byte-for-byte — nothing downstream may "fix" the text.
3. Normalized text lives in a separate field and is never written back over
   verbatim.

Layer 2 runs the mock provider (deterministic; the mock never edits text) so
it gates OUR pipeline. A live-provider golden run against real sample photos
is `test_live_claude_verbatim`, skipped without an API key.
"""

from __future__ import annotations

import os

import pytest

from hwportfolio import storage
from hwportfolio.db import session_scope
from hwportfolio.models import Artifact, Assignment, Batch, Extraction
from hwportfolio.pipeline.runner import process_artifact
from hwportfolio.transcribe.mock import MockProvider
from hwportfolio.transcribe.verbatim_prompt import (
    REQUIRED_PROHIBITIONS,
    VERBATIM_SYSTEM_PROMPT,
)

from .golden_set import GOLDEN_CASES
from .synth import add_rules, blank_page, write_lines

import cv2


def test_verbatim_prompt_contains_all_prohibitions():
    for phrase in REQUIRED_PROHIBITIONS:
        assert phrase in VERBATIM_SYSTEM_PROMPT, (
            f"Verbatim prompt lost required prohibition: {phrase!r}. "
            "This is our core differentiator (GOALS T2) — do not ship."
        )


def _make_artifact_with_text(verbatim: str) -> str:
    """Synthesize a page, register provider ground truth for the segmented
    region crop, store the artifact, return artifact_id."""
    page = blank_page()
    add_rules(page)
    write_lines(page, [verbatim])

    # Register ground truth for the crop the pipeline will actually produce.
    from hwportfolio.pipeline.deskew import deskew
    from hwportfolio.pipeline.segment import segment

    result = deskew(page)
    seg = segment(cv2.cvtColor(result.image, cv2.COLOR_BGR2GRAY))
    assert seg.regions, "Synthetic page produced no regions"
    r = seg.regions[0]
    crop = result.image[r["y"]:r["y"] + r["h"], r["x"]:r["x"] + r["w"]]
    MockProvider.register_ground_truth(crop, verbatim)

    ok, buffer = cv2.imencode(".png", page)
    assert ok
    uri = storage.store_bytes(buffer.tobytes())
    with session_scope() as session:
        assignment = Assignment(title="golden")
        session.add(assignment)
        session.flush()
        batch = Batch(assignment_id=assignment.id)
        session.add(batch)
        session.flush()
        artifact = Artifact(batch_id=batch.id, assignment_id=assignment.id, image_uri=uri)
        session.add(artifact)
        session.flush()
        return artifact.id


@pytest.mark.parametrize("verbatim,normalized_form", GOLDEN_CASES)
def test_pipeline_preserves_invented_spelling(verbatim: str, normalized_form: str):
    artifact_id = _make_artifact_with_text(verbatim)
    process_artifact(artifact_id, provider_name="mock")

    with session_scope() as session:
        artifact = session.get(Artifact, artifact_id)
        extractions = [e for region in artifact.regions for e in region.extractions]
        assert extractions, "Pipeline stored no extraction"
        stored = [e for e in extractions if e.verbatim]
        assert stored, "Pipeline stored only empty extractions"
        extraction = stored[0]

        # THE gate: byte-for-byte preservation. Not "mostly right".
        assert extraction.verbatim == verbatim, (
            f"Verbatim was altered in the pipeline: {extraction.verbatim!r} "
            f"!= {verbatim!r}. If it drifted toward {normalized_form!r}, "
            "something is normalizing — this fails CI by design."
        )
        # Verbatim must never equal a normalization the page doesn't contain.
        if normalized_form != verbatim:
            assert extraction.verbatim != normalized_form


def test_normalized_is_separate_and_verbatim_untouched():
    verbatim = "I wnt to the stor"
    artifact_id = _make_artifact_with_text(verbatim)
    process_artifact(artifact_id, provider_name="mock")
    with session_scope() as session:
        artifact = session.get(Artifact, artifact_id)
        extraction = next(
            e for region in artifact.regions for e in region.extractions if e.verbatim
        )
        assert extraction.verbatim == verbatim
        assert extraction.normalized == "I went to the store"
        assert extraction.normalized != extraction.verbatim
        # Model version recorded, always (GOALS §6).
        assert extraction.provider and extraction.model_version


def test_tokens_carry_confidence_and_illegible_flag():
    verbatim = "the cat sed meow"
    artifact_id = _make_artifact_with_text(verbatim)
    process_artifact(artifact_id, provider_name="mock")
    with session_scope() as session:
        extraction = (
            session.query(Extraction).filter(Extraction.verbatim == verbatim).one()
        )
        assert extraction.tokens, "Per-token record missing"
        for token in extraction.tokens:
            assert set(token) == {"text", "confidence", "illegible"}
            assert 0.0 <= token["confidence"] <= 1.0


@pytest.mark.skipif(
    not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("HWP_ANTHROPIC_API_KEY")),
    reason="No Anthropic API key; live golden run skipped",
)
def test_live_claude_verbatim_smoke():
    """Live provider smoke test: the model must not correct 'wnt' -> 'went'
    on a clean rendered sample. Real handwriting photos are the Phase 0 set."""
    from hwportfolio.transcribe.claude import ClaudeProvider

    page = blank_page()
    write_lines(page, ["I wnt to the stor"], start_y=200)
    provider = ClaudeProvider()
    result = provider.transcribe(page)
    assert "wnt" in result.verbatim
    assert "went" not in result.verbatim
