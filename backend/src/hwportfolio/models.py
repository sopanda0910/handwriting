"""Data model. See GOALS.md §6 — names matter, get them right early.

Non-negotiable properties enforced here:

* Every model output (Extraction, Observation) carries provider/model version.
* Nothing is deleted, only superseded: corrections create a new row pointing at
  the old one via ``supersedes_id``.
* Uncommitted extractions/observations are a *distinct state*
  (``ReviewState.provisional``), not a nullable flag. ``committed_at`` exists as
  a timestamp but state transitions go through the enum.
* An Observation without a bounding box cannot be constructed (validator below).
  No pixel provenance, no record.
* Students carry no PII beyond a display name and internal/external IDs.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class ReviewState(str, enum.Enum):
    provisional = "provisional"  # model output, teacher has not confirmed
    committed = "committed"      # teacher explicitly confirmed (GOALS §7 C4)
    superseded = "superseded"    # replaced by a newer record; kept forever
    rejected = "rejected"        # teacher discarded; kept forever
    suppressed = "suppressed"    # auto-suppressed (e.g. unruled paper), never shown


class School(Base):
    __tablename__ = "schools"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    teachers: Mapped[list["Teacher"]] = relationship(back_populates="school")


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"))
    display_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    school: Mapped[School] = relationship(back_populates="teachers")
    classrooms: Mapped[list["Classroom"]] = relationship(back_populates="teacher")


class Classroom(Base):
    """One teacher's class for one school year. Rosters, assignments, and
    therefore batches and timelines all hang off a classroom."""

    __tablename__ = "classrooms"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"))
    name: Mapped[str] = mapped_column(String(200))  # e.g. "Room 12 — Grade 1"
    grade_band: Mapped[str] = mapped_column(String(8))
    school_year: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    teacher: Mapped[Teacher] = relationship(back_populates="classrooms")
    students: Mapped[list["Student"]] = relationship(back_populates="classroom")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    classroom_id: Mapped[str | None] = mapped_column(
        ForeignKey("classrooms.id"), nullable=True, index=True
    )
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    grade_band: Mapped[str] = mapped_column(String(8))  # "K", "1" .. "5"
    school_year: Mapped[str] = mapped_column(String(16))  # e.g. "2026-2027"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    classroom: Mapped[Classroom | None] = relationship(back_populates="students")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="student")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    classroom_id: Mapped[str | None] = mapped_column(
        ForeignKey("classrooms.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(32), default="writing")  # writing|math|worksheet|other
    subject: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expectations: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Batch(Base):
    """One capture session: a stack of pages uploaded together."""

    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"))
    status: Mapped[str] = mapped_column(String(32), default="created")
    # created -> processing -> ready_for_review -> done / failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="batch")


class Artifact(Base):
    """One physical page."""

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"))
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"))
    student_id: Mapped[str | None] = mapped_column(ForeignKey("students.id"), nullable=True)
    student_match_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # qr | manual | None (unmatched)
    image_uri: Mapped[str] = mapped_column(String(500))
    capture_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    deskew_transform: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ruled_paper: Mapped[bool | None] = mapped_column(nullable=True)  # None = not yet analyzed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    batch: Mapped[Batch] = relationship(back_populates="artifacts")
    student: Mapped[Student | None] = relationship(back_populates="artifacts")
    regions: Mapped[list["Region"]] = relationship(back_populates="artifact")
    observations: Mapped[list["Observation"]] = relationship(back_populates="artifact")


class Region(Base):
    """A bounding box on an Artifact; the unit of transcription."""

    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(16), default="prose")  # prose|math|drawing|header
    x: Mapped[int] = mapped_column(Integer)
    y: Mapped[int] = mapped_column(Integer)
    w: Mapped[int] = mapped_column(Integer)
    h: Mapped[int] = mapped_column(Integer)

    artifact: Mapped[Artifact] = relationship(back_populates="regions")
    extractions: Mapped[list["Extraction"]] = relationship(back_populates="region")


class Extraction(Base):
    """Verbatim + normalized text for a Region.

    ``verbatim`` is exactly what is on the page, student errors included.
    ``normalized`` is generated in a separate call from the verbatim *string*
    (never from the image) and is never shown as "what the student wrote".
    """

    __tablename__ = "extractions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    region_id: Mapped[str] = mapped_column(ForeignKey("regions.id"))
    verbatim: Mapped[str] = mapped_column(Text)
    normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Per-token record: [{"text": str, "confidence": float, "illegible": bool}]
    # "genuinely illegible" is distinct from "legible but non-standard".
    tokens: Mapped[list] = mapped_column(JSON, default=list)
    provider: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(16), default="model")  # model|teacher
    state: Mapped[ReviewState] = mapped_column(
        Enum(ReviewState), default=ReviewState.provisional
    )
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("extractions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    region: Mapped[Region] = relationship(back_populates="extractions")


class Observation(Base):
    """One image-space finding. Type, magnitude, bounding box, model version.

    Never names a condition (GOALS §7 C1). Magnitudes are raw measurements against
    the student's own work — never a peer-relative rank.
    """

    __tablename__ = "observations"
    __table_args__ = (
        CheckConstraint("w > 0 AND h > 0", name="observation_bbox_nonempty"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"))
    type: Mapped[str] = mapped_column(String(64), index=True)
    # e.g. baseline_adherence, xheight_consistency, spacing_ratio,
    #      slant_consistency, reversal_candidate, line_drift
    magnitude: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    # Pixel provenance — required. An observation without a bounding box is
    # rejected at construction time; see validates() below.
    x: Mapped[int] = mapped_column(Integer)
    y: Mapped[int] = mapped_column(Integer)
    w: Mapped[int] = mapped_column(Integer)
    h: Mapped[int] = mapped_column(Integer)
    model_version: Mapped[str] = mapped_column(String(128))
    state: Mapped[ReviewState] = mapped_column(
        Enum(ReviewState), default=ReviewState.provisional
    )
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("observations.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    artifact: Mapped[Artifact] = relationship(back_populates="observations")

    @validates("w", "h")
    def _require_bbox(self, key: str, value: int) -> int:
        if value is None or value <= 0:
            raise ValueError(
                "Observation requires pixel provenance: bounding box "
                f"{key} must be a positive integer (got {value!r})."
            )
        return value

    @validates("x", "y")
    def _require_bbox_origin(self, key: str, value: int) -> int:
        if value is None or value < 0:
            raise ValueError(
                f"Observation bounding box {key} must be a non-negative integer."
            )
        return value


class Skill(Base):
    """A curriculum-anchored construct from the versioned taxonomy in /config/skills/."""

    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    # e.g. letter_formation.reversals.bd, spelling.stage.semi_phonetic
    label: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(64))
    taxonomy_version: Mapped[str] = mapped_column(String(32))


class SkillEvidence(Base):
    """Links an Observation *or* an Extraction to a Skill.

    This is the join that makes the timeline queryable. Exactly one of
    observation_id / extraction_id is set (DB-level check).
    """

    __tablename__ = "skill_evidence"
    __table_args__ = (
        CheckConstraint(
            "(observation_id IS NULL) != (extraction_id IS NULL)",
            name="skill_evidence_exactly_one_source",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    observation_id: Mapped[str | None] = mapped_column(ForeignKey("observations.id"), nullable=True)
    extraction_id: Mapped[str | None] = mapped_column(ForeignKey("extractions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TimelineEntry(Base):
    """Materialized per-student view for fast portal reads.

    Written only at teacher commit time (GOALS §7 C4): nothing reaches the
    timeline without an explicit commit.
    """

    __tablename__ = "timeline_entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    entry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    kind: Mapped[str] = mapped_column(String(32))  # extraction | observation
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"))
    extraction_id: Mapped[str | None] = mapped_column(ForeignKey("extractions.id"), nullable=True)
    observation_id: Mapped[str | None] = mapped_column(ForeignKey("observations.id"), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class ShareGrant(Base):
    """Parent access: expiring token, scoped to one student, revocable."""

    __tablename__ = "share_grants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Teacher curates what is shared; default is share-nothing.
    included_entry_ids: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    access_log: Mapped[list["ShareAccessLog"]] = relationship(back_populates="grant")


class ShareAccessLog(Base):
    """Audit log on every parent-share read (GOALS §7 C3)."""

    __tablename__ = "share_access_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    grant_id: Mapped[str] = mapped_column(ForeignKey("share_grants.id"), index=True)
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    remote_addr: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)

    grant: Mapped[ShareGrant] = relationship(back_populates="access_log")


class Job(Base):
    """Queue bookkeeping so batch progress is inspectable from the UI."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    # queued -> running -> done / failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
