"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Org hierarchy ---

class SchoolCreate(BaseModel):
    name: str


class SchoolOut(ORMModel):
    id: str
    name: str


class TeacherCreate(BaseModel):
    school_id: str
    display_name: str
    email: str


class TeacherOut(ORMModel):
    id: str
    school_id: str
    display_name: str
    email: str


class ClassroomCreate(BaseModel):
    teacher_id: str
    name: str
    grade_band: str
    school_year: str


class ClassroomOut(ORMModel):
    id: str
    teacher_id: str
    name: str
    grade_band: str
    school_year: str


# --- Students ---

class StudentCreate(BaseModel):
    external_id: str
    display_name: str
    grade_band: str
    school_year: str
    classroom_id: str | None = None


class StudentOut(ORMModel):
    id: str
    external_id: str
    display_name: str
    grade_band: str
    school_year: str
    classroom_id: str | None


# --- Assignments ---

class AssignmentCreate(BaseModel):
    title: str
    kind: str = "writing"
    subject: str | None = None
    expectations: str | None = None
    classroom_id: str | None = None


class AssignmentOut(ORMModel):
    id: str
    title: str
    kind: str
    subject: str | None
    expectations: str | None
    classroom_id: str | None


# --- Batches / artifacts ---

class BatchOut(ORMModel):
    id: str
    assignment_id: str
    status: str
    error: str | None
    created_at: datetime


class RegionOut(ORMModel):
    id: str
    order_index: int
    kind: str
    x: int
    y: int
    w: int
    h: int


class ExtractionOut(ORMModel):
    id: str
    region_id: str
    verbatim: str
    normalized: str | None
    tokens: list
    provider: str
    model_version: str
    source: str
    state: str
    supersedes_id: str | None
    created_at: datetime


class ObservationOut(ORMModel):
    id: str
    artifact_id: str
    type: str
    magnitude: float
    unit: str
    details: dict
    x: int
    y: int
    w: int
    h: int
    model_version: str
    state: str
    created_at: datetime


class ArtifactOut(ORMModel):
    id: str
    batch_id: str
    assignment_id: str
    student_id: str | None
    student_match_method: str | None
    image_uri: str
    ruled_paper: bool | None
    created_at: datetime


class ArtifactDetail(ArtifactOut):
    regions: list[RegionOut] = []
    observations: list[ObservationOut] = []


# --- Review actions ---

class ExtractionCorrection(BaseModel):
    verbatim: str
    normalized: str | None = None


class AssignStudent(BaseModel):
    student_id: str


# --- Timeline ---

class TimelineEntryOut(ORMModel):
    id: str
    student_id: str
    entry_date: datetime
    kind: str
    artifact_id: str
    extraction_id: str | None
    observation_id: str | None
    summary: str
    payload: dict


# --- Share grants ---

class ShareGrantCreate(BaseModel):
    student_id: str
    included_entry_ids: list[str] = []  # default is share-nothing
    note: str | None = None
    ttl_hours: int | None = None


class ShareGrantOut(ORMModel):
    id: str
    student_id: str
    token: str
    included_entry_ids: list
    note: str | None
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class SharedTimelineView(BaseModel):
    student_name: str
    note: str | None
    entries: list[TimelineEntryOut]
