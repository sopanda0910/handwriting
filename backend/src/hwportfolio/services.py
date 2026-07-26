"""Commit-time domain logic.

Teacher-in-the-loop is structural (GOALS §7 C4): TimelineEntry rows — the only
thing the portal and parent views read — are created exclusively here, and
only from an explicit commit call. There is no auto-approve path; if you find
yourself adding one, stop and raise it.

Nothing is deleted, only superseded: corrections create a new row pointing at
the old one via supersedes_id.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import (
    Artifact,
    Extraction,
    Observation,
    Region,
    ReviewState,
    Skill,
    SkillEvidence,
    TimelineEntry,
    utcnow,
)

# Observation type -> skill key (taxonomy in /config/skills/). Extraction
# evidence mapping (spelling stages) needs content analysis and is Phase 2.
OBSERVATION_SKILL_MAP = {
    "reversal_candidate": "letter_formation.reversals.bd",
    "baseline_adherence": "letter_formation.baseline",
    "xheight_consistency": "letter_formation.size_consistency",
    "ascender_descender_ratio": "letter_formation.proportion",
    "spacing_ratio": "spacing.word_boundaries",
    "slant_consistency": "letter_formation.slant",
    "line_drift": "letter_formation.baseline",
}


def _student_for_artifact(session: Session, artifact: Artifact) -> str:
    if artifact.student_id is None:
        raise ValueError(
            "Artifact is not matched to a student; assign a student before committing."
        )
    return artifact.student_id


def commit_extraction(session: Session, extraction: Extraction) -> TimelineEntry:
    if extraction.state == ReviewState.committed:
        raise ValueError("Extraction is already committed.")
    if extraction.state == ReviewState.superseded:
        raise ValueError("Cannot commit a superseded extraction; commit its replacement.")
    region = session.get(Region, extraction.region_id)
    artifact = session.get(Artifact, region.artifact_id)
    student_id = _student_for_artifact(session, artifact)

    extraction.state = ReviewState.committed
    extraction.committed_at = utcnow()

    snippet = extraction.verbatim.strip().replace("\n", " ")
    if len(snippet) > 80:
        snippet = snippet[:77] + "..."
    entry = TimelineEntry(
        student_id=student_id,
        kind="extraction",
        artifact_id=artifact.id,
        extraction_id=extraction.id,
        summary=f'Wrote: "{snippet}"' if snippet else "Writing sample recorded",
        payload={
            "verbatim": extraction.verbatim,
            "region": {"x": region.x, "y": region.y, "w": region.w, "h": region.h},
            "provider": extraction.provider,
            "model_version": extraction.model_version,
        },
    )
    session.add(entry)
    return entry


def correct_extraction(
    session: Session, extraction: Extraction, verbatim: str, normalized: str | None
) -> Extraction:
    """Teacher correction: supersede, never edit in place.

    The correction stream is our best training signal (GOALS §6).
    """
    replacement = Extraction(
        region_id=extraction.region_id,
        verbatim=verbatim,
        normalized=normalized,
        tokens=[],
        provider="teacher",
        model_version="teacher",
        source="teacher",
        state=ReviewState.provisional,
        supersedes_id=extraction.id,
    )
    extraction.state = ReviewState.superseded
    session.add(replacement)
    session.flush()
    return replacement


def commit_observation(session: Session, observation: Observation) -> TimelineEntry:
    if observation.state == ReviewState.committed:
        raise ValueError("Observation is already committed.")
    if observation.state == ReviewState.suppressed:
        raise ValueError("Suppressed observations cannot be committed.")
    artifact = session.get(Artifact, observation.artifact_id)
    student_id = _student_for_artifact(session, artifact)

    observation.state = ReviewState.committed
    observation.committed_at = utcnow()

    # Observational summary — a measurement, never an interpretation.
    if observation.type == "reversal_candidate":
        shape = observation.details.get("shape", "?")
        summary = f'Letter formed as "{shape}" flagged for review (confirmed by teacher)'
    else:
        summary = (
            f"{observation.type.replace('_', ' ')}: "
            f"{observation.magnitude:.2f} {observation.unit}"
        )

    entry = TimelineEntry(
        student_id=student_id,
        kind="observation",
        artifact_id=artifact.id,
        observation_id=observation.id,
        summary=summary,
        payload={
            "type": observation.type,
            "magnitude": observation.magnitude,
            "unit": observation.unit,
            "bbox": {"x": observation.x, "y": observation.y,
                     "w": observation.w, "h": observation.h},
            "model_version": observation.model_version,
        },
    )
    session.add(entry)

    skill_key = OBSERVATION_SKILL_MAP.get(observation.type)
    if skill_key is not None:
        skill = session.query(Skill).filter(Skill.key == skill_key).one_or_none()
        if skill is not None:
            session.add(SkillEvidence(
                skill_id=skill.id,
                student_id=student_id,
                observation_id=observation.id,
            ))
    return entry


def reject(session: Session, record: Extraction | Observation) -> None:
    if record.state == ReviewState.committed:
        raise ValueError("Cannot reject a committed record; supersede it instead.")
    record.state = ReviewState.rejected
