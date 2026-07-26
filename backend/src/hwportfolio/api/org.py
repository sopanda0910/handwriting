"""School -> Teacher -> Classroom hierarchy.

Alpha scope: registration and lookup only — no authentication yet. When
accounts land, the teacher becomes the authenticated principal and classroom
scoping becomes enforcement rather than convenience.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Classroom, School, Teacher
from ..schemas import (
    ClassroomCreate,
    ClassroomOut,
    SchoolCreate,
    SchoolOut,
    TeacherCreate,
    TeacherOut,
)

router = APIRouter(prefix="/api", tags=["org"])


@router.post("/schools", response_model=SchoolOut)
def create_school(body: SchoolCreate, session: Session = Depends(get_session)):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "School name is required")
    existing = session.query(School).filter(School.name == name).one_or_none()
    if existing is not None:
        return existing  # idempotent registration by name
    school = School(name=name)
    session.add(school)
    session.flush()
    return school


@router.get("/schools", response_model=list[SchoolOut])
def list_schools(session: Session = Depends(get_session)):
    return session.query(School).order_by(School.name).all()


@router.post("/teachers", response_model=TeacherOut)
def create_teacher(body: TeacherCreate, session: Session = Depends(get_session)):
    if session.get(School, body.school_id) is None:
        raise HTTPException(404, "Unknown school")
    email = body.email.strip().lower()
    existing = session.query(Teacher).filter(Teacher.email == email).one_or_none()
    if existing is not None:
        if existing.school_id != body.school_id:
            raise HTTPException(409, "Email already registered at a different school")
        return existing
    teacher = Teacher(
        school_id=body.school_id,
        display_name=body.display_name.strip(),
        email=email,
    )
    session.add(teacher)
    session.flush()
    return teacher


@router.get("/teachers", response_model=list[TeacherOut])
def list_teachers(school_id: str | None = None, session: Session = Depends(get_session)):
    query = session.query(Teacher).order_by(Teacher.display_name)
    if school_id is not None:
        query = query.filter(Teacher.school_id == school_id)
    return query.all()


@router.post("/classrooms", response_model=ClassroomOut)
def create_classroom(body: ClassroomCreate, session: Session = Depends(get_session)):
    if session.get(Teacher, body.teacher_id) is None:
        raise HTTPException(404, "Unknown teacher")
    classroom = Classroom(
        teacher_id=body.teacher_id,
        name=body.name.strip(),
        grade_band=body.grade_band,
        school_year=body.school_year,
    )
    session.add(classroom)
    session.flush()
    return classroom


@router.get("/classrooms", response_model=list[ClassroomOut])
def list_classrooms(teacher_id: str | None = None, session: Session = Depends(get_session)):
    query = session.query(Classroom).order_by(Classroom.created_at)
    if teacher_id is not None:
        query = query.filter(Classroom.teacher_id == teacher_id)
    return query.all()


@router.get("/classrooms/{classroom_id}", response_model=ClassroomOut)
def get_classroom(classroom_id: str, session: Session = Depends(get_session)):
    classroom = session.get(Classroom, classroom_id)
    if classroom is None:
        raise HTTPException(404, "Unknown classroom")
    return classroom
