"""Review endpoints — the review step is the product, not a formality.

Every mutation here is an explicit teacher action (GOALS §7 C4).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import services
from ..db import get_session
from ..models import Artifact, Extraction, Observation, Student
from ..schemas import (
    AssignStudent,
    ExtractionCorrection,
    ExtractionOut,
    ObservationOut,
    TimelineEntryOut,
)

router = APIRouter(prefix="/api/review", tags=["review"])


def _get_or_404(session: Session, model, record_id: str):
    record = session.get(model, record_id)
    if record is None:
        raise HTTPException(404, f"Unknown {model.__name__}")
    return record


@router.post("/artifacts/{artifact_id}/assign-student")
def assign_student(
    artifact_id: str, body: AssignStudent, session: Session = Depends(get_session)
):
    artifact = _get_or_404(session, Artifact, artifact_id)
    _get_or_404(session, Student, body.student_id)
    artifact.student_id = body.student_id
    artifact.student_match_method = "manual"
    return {"ok": True}


@router.post("/extractions/{extraction_id}/commit", response_model=TimelineEntryOut)
def commit_extraction(extraction_id: str, session: Session = Depends(get_session)):
    extraction = _get_or_404(session, Extraction, extraction_id)
    try:
        entry = services.commit_extraction(session, extraction)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    session.flush()
    return entry


@router.post("/extractions/{extraction_id}/correct", response_model=ExtractionOut)
def correct_extraction(
    extraction_id: str, body: ExtractionCorrection, session: Session = Depends(get_session)
):
    extraction = _get_or_404(session, Extraction, extraction_id)
    replacement = services.correct_extraction(
        session, extraction, body.verbatim, body.normalized
    )
    return replacement


@router.post("/extractions/{extraction_id}/reject")
def reject_extraction(extraction_id: str, session: Session = Depends(get_session)):
    extraction = _get_or_404(session, Extraction, extraction_id)
    try:
        services.reject(session, extraction)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.post("/observations/{observation_id}/commit", response_model=TimelineEntryOut)
def commit_observation(observation_id: str, session: Session = Depends(get_session)):
    observation = _get_or_404(session, Observation, observation_id)
    try:
        entry = services.commit_observation(session, observation)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    session.flush()
    return entry


@router.post("/observations/{observation_id}/reject")
def reject_observation(observation_id: str, session: Session = Depends(get_session)):
    observation = _get_or_404(session, Observation, observation_id)
    try:
        services.reject(session, observation)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.get("/observations/{observation_id}", response_model=ObservationOut)
def get_observation(observation_id: str, session: Session = Depends(get_session)):
    return _get_or_404(session, Observation, observation_id)
