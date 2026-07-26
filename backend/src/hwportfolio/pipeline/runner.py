"""The batch pipeline (GOALS §5.1):

capture → deskew/segment → roster match → [transcribe] + [observe] → review → commit

Transcription and observation are parallel, independent branches: neither sees
the other's output, and nothing here couples them. Everything written by this
runner is provisional (ReviewState.provisional) — the teacher's commit in the
review UI is what makes a record real.
"""

from __future__ import annotations

import cv2
import numpy as np

from .. import storage
from ..db import session_scope
from ..jobs.queue import register_handler
from ..models import (
    Artifact,
    Batch,
    Extraction,
    Observation,
    Region,
    ReviewState,
    Student,
)
from ..observe import OBSERVE_MODEL_VERSION
from ..observe.features import (
    ascender_descender_ratio,
    baseline_adherence,
    line_drift,
    slant_consistency,
    spacing_ratio,
    xheight_consistency,
)
from ..observe.reversals import detect_reversal_candidates
from ..transcribe import get_provider
from . import deskew as deskew_mod
from . import roster, segment as segment_mod


def load_image(uri: str) -> np.ndarray:
    path = storage.resolve(uri)
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image at {path}")
    return image


def process_artifact(artifact_id: str, provider_name: str | None = None) -> None:
    with session_scope() as session:
        artifact = session.get(Artifact, artifact_id)
        if artifact is None:
            raise ValueError(f"Unknown artifact {artifact_id}")
        image_uri = artifact.image_uri

    image = load_image(image_uri)

    # --- Deskew ---
    result = deskew_mod.deskew(image)
    gray = cv2.cvtColor(result.image, cv2.COLOR_BGR2GRAY)

    # --- Roster match (QR header) ---
    match = roster.detect(result.image)
    matched_student_id: str | None = None
    if match is not None:
        with session_scope() as session:
            student = (
                session.query(Student)
                .filter(Student.external_id == match.external_id)
                .one_or_none()
            )
            if student is not None:
                matched_student_id = student.id

    # --- Segment ---
    seg = segment_mod.segment(gray)

    with session_scope() as session:
        artifact = session.get(Artifact, artifact_id)
        artifact.deskew_transform = result.transform
        artifact.ruled_paper = seg.ruled
        if matched_student_id is not None:
            artifact.student_id = matched_student_id
            artifact.student_match_method = "qr"
        region_rows = []
        for index, region in enumerate(seg.regions):
            row = Region(
                artifact_id=artifact_id,
                order_index=index,
                kind=region["kind"],
                x=region["x"], y=region["y"], w=region["w"], h=region["h"],
            )
            session.add(row)
            region_rows.append(row)
        session.flush()
        region_ids = [(r.id, (r.x, r.y, r.w, r.h)) for r in region_rows]

    # --- Branch 1: transcription (text space) ---
    provider = get_provider(provider_name)
    for region_id, (x, y, w, h) in region_ids:
        crop = result.image[y:y + h, x:x + w]
        transcription = provider.transcribe(crop)
        normalized = provider.normalize(transcription.verbatim) if transcription.verbatim else None
        with session_scope() as session:
            session.add(Extraction(
                region_id=region_id,
                verbatim=transcription.verbatim,
                normalized=normalized,
                tokens=transcription.to_token_dicts(),
                provider=transcription.provider,
                model_version=transcription.model_version,
                source="model",
                state=ReviewState.provisional,
            ))

    # --- Branch 2: observation (image space) — never sees transcription output ---
    candidates = []
    candidates += baseline_adherence(gray, seg.lines, seg.rule_ys, seg.ruled)
    candidates += xheight_consistency(gray, seg.lines)
    candidates += ascender_descender_ratio(gray, seg.lines)
    candidates += spacing_ratio(gray, seg.lines)
    candidates += slant_consistency(gray, seg.lines)
    candidates += line_drift(gray, seg.lines, seg.ruled)
    candidates += detect_reversal_candidates(gray, seg.lines)

    with session_scope() as session:
        for c in candidates:
            session.add(Observation(
                artifact_id=artifact_id,
                type=c.type,
                magnitude=c.magnitude,
                unit=c.unit,
                details=c.details,
                x=c.x, y=c.y, w=c.w, h=c.h,
                model_version=OBSERVE_MODEL_VERSION,
                state=ReviewState.suppressed if c.suppressed else ReviewState.provisional,
            ))


@register_handler("process_batch")
def process_batch(payload: dict) -> None:
    batch_id = payload["batch_id"]
    provider_name = payload.get("provider")
    with session_scope() as session:
        batch = session.get(Batch, batch_id)
        if batch is None:
            raise ValueError(f"Unknown batch {batch_id}")
        batch.status = "processing"
        artifact_ids = [a.id for a in batch.artifacts]

    errors: list[str] = []
    for artifact_id in artifact_ids:
        try:
            process_artifact(artifact_id, provider_name)
        except Exception as exc:  # keep going; one bad page must not sink the batch
            errors.append(f"{artifact_id}: {exc}")

    with session_scope() as session:
        batch = session.get(Batch, batch_id)
        batch.status = "ready_for_review"
        batch.error = "\n".join(errors) if errors else None
