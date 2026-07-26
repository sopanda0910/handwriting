"""Parent share grants (GOALS §4, §6, §7 C3).

Teacher-initiated, read-only, expiring, revocable, scoped to one student.
Default is share-nothing — the teacher curates exactly which timeline entries
a parent sees. Every read is audit-logged.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_session
from ..models import ShareAccessLog, ShareGrant, Student, TimelineEntry, utcnow
from ..safety import check_text
from ..schemas import ShareGrantCreate, ShareGrantOut, SharedTimelineView

router = APIRouter(prefix="/api", tags=["shares"])


@router.post("/shares", response_model=ShareGrantOut)
def create_share(body: ShareGrantCreate, session: Session = Depends(get_session)):
    student = session.get(Student, body.student_id)
    if student is None:
        raise HTTPException(404, "Unknown student")

    # Teacher-authored note renders in front of a parent under our name —
    # the observational-language constraint applies (GOALS §7 C1).
    if body.note:
        try:
            check_text(body.note)
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    # Only committed entries belonging to this student may be shared.
    if body.included_entry_ids:
        rows = (
            session.query(TimelineEntry)
            .filter(TimelineEntry.id.in_(body.included_entry_ids))
            .all()
        )
        if len(rows) != len(set(body.included_entry_ids)):
            raise HTTPException(400, "Unknown timeline entry in included_entry_ids")
        for row in rows:
            if row.student_id != body.student_id:
                raise HTTPException(400, "Timeline entry belongs to a different student")

    ttl = body.ttl_hours or settings.share_grant_ttl_hours
    grant = ShareGrant(
        student_id=body.student_id,
        token=secrets.token_urlsafe(32),
        included_entry_ids=body.included_entry_ids,
        note=body.note,
        expires_at=utcnow() + timedelta(hours=ttl),
    )
    session.add(grant)
    session.flush()
    return grant


@router.post("/shares/{grant_id}/revoke", response_model=ShareGrantOut)
def revoke_share(grant_id: str, session: Session = Depends(get_session)):
    grant = session.get(ShareGrant, grant_id)
    if grant is None:
        raise HTTPException(404, "Unknown share grant")
    if grant.revoked_at is None:
        grant.revoked_at = utcnow()
    return grant


@router.get("/shares/{grant_id}/access-log")
def share_access_log(grant_id: str, session: Session = Depends(get_session)):
    grant = session.get(ShareGrant, grant_id)
    if grant is None:
        raise HTTPException(404, "Unknown share grant")
    return [
        {
            "accessed_at": log.accessed_at,
            "remote_addr": log.remote_addr,
            "user_agent": log.user_agent,
        }
        for log in grant.access_log
    ]


@router.get("/shared/{token}", response_model=SharedTimelineView)
def view_shared(token: str, request: Request, session: Session = Depends(get_session)):
    """The parent-facing view. No login; the expiring token is the credential."""
    grant = session.query(ShareGrant).filter(ShareGrant.token == token).one_or_none()
    if grant is None:
        raise HTTPException(404, "Unknown or expired share link")
    now = utcnow()
    expires = grant.expires_at
    if expires.tzinfo is None:
        from datetime import timezone
        expires = expires.replace(tzinfo=timezone.utc)
    if grant.revoked_at is not None or expires < now:
        raise HTTPException(410, "This share link has expired or been revoked")

    session.add(ShareAccessLog(
        grant_id=grant.id,
        remote_addr=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    ))

    student = session.get(Student, grant.student_id)
    entries = []
    if grant.included_entry_ids:
        entries = (
            session.query(TimelineEntry)
            .filter(TimelineEntry.id.in_(grant.included_entry_ids))
            .order_by(TimelineEntry.entry_date)
            .all()
        )
    return SharedTimelineView(
        student_name=student.display_name,
        note=grant.note,
        entries=entries,
    )
