from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Student, TimelineEntry
from ..schemas import TimelineEntryOut

router = APIRouter(prefix="/api", tags=["timeline"])


@router.get("/students/{student_id}/timeline", response_model=list[TimelineEntryOut])
def student_timeline(
    student_id: str,
    kind: str | None = None,
    observation_type: str | None = None,
    session: Session = Depends(get_session),
):
    """The per-student record. Trajectory against the student's own baseline —
    there is intentionally no cross-student endpoint, no ranking, no
    leaderboard (GOALS §7 C2)."""
    if session.get(Student, student_id) is None:
        raise HTTPException(404, "Unknown student")
    query = (
        session.query(TimelineEntry)
        .filter(TimelineEntry.student_id == student_id)
        .order_by(TimelineEntry.entry_date)
    )
    if kind is not None:
        query = query.filter(TimelineEntry.kind == kind)
    entries = query.all()
    if observation_type is not None:
        entries = [e for e in entries if e.payload.get("type") == observation_type]
    return entries
