from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Classroom, Student
from ..pipeline import roster
from ..schemas import StudentCreate, StudentOut

router = APIRouter(prefix="/api/students", tags=["students"])


@router.post("", response_model=StudentOut)
def create_student(body: StudentCreate, session: Session = Depends(get_session)):
    exists = session.query(Student).filter(Student.external_id == body.external_id).first()
    if exists:
        raise HTTPException(409, f"Student with external_id {body.external_id!r} exists")
    if body.classroom_id is not None and session.get(Classroom, body.classroom_id) is None:
        raise HTTPException(404, "Unknown classroom")
    student = Student(**body.model_dump())
    session.add(student)
    session.flush()
    return student


@router.get("", response_model=list[StudentOut])
def list_students(classroom_id: str | None = None, session: Session = Depends(get_session)):
    query = session.query(Student).order_by(Student.display_name)
    if classroom_id is not None:
        query = query.filter(Student.classroom_id == classroom_id)
    return query.all()


@router.get("/{student_id}/qr.png")
def student_qr(student_id: str, session: Session = Depends(get_session)):
    """Printable QR header label for roster matching (docs/decisions/0002)."""
    student = session.get(Student, student_id)
    if student is None:
        raise HTTPException(404, "Unknown student")
    png = roster.render_qr_png(student.external_id, student.display_name)
    return Response(content=png, media_type="image/png")
