from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import storage
from ..db import get_session
from ..jobs import get_queue
from ..models import Artifact, Assignment, Batch
from ..schemas import (
    ArtifactDetail,
    ArtifactOut,
    AssignmentCreate,
    AssignmentOut,
    BatchOut,
    ExtractionOut,
)

router = APIRouter(prefix="/api", tags=["batches"])

ALLOWED_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


@router.post("/assignments", response_model=AssignmentOut)
def create_assignment(body: AssignmentCreate, session: Session = Depends(get_session)):
    if body.classroom_id is not None:
        from ..models import Classroom

        if session.get(Classroom, body.classroom_id) is None:
            raise HTTPException(404, "Unknown classroom")
    assignment = Assignment(**body.model_dump())
    session.add(assignment)
    session.flush()
    return assignment


@router.get("/assignments", response_model=list[AssignmentOut])
def list_assignments(classroom_id: str | None = None, session: Session = Depends(get_session)):
    query = session.query(Assignment).order_by(Assignment.created_at.desc())
    if classroom_id is not None:
        query = query.filter(Assignment.classroom_id == classroom_id)
    return query.all()


@router.post("/assignments/{assignment_id}/batches", response_model=BatchOut)
async def create_batch(
    assignment_id: str,
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
):
    """Upload a class set of page images and kick off the async pipeline."""
    if session.get(Assignment, assignment_id) is None:
        raise HTTPException(404, "Unknown assignment")
    if not files:
        raise HTTPException(400, "No files uploaded")

    batch = Batch(assignment_id=assignment_id, status="created")
    session.add(batch)
    session.flush()

    for upload in files:
        suffix = ALLOWED_TYPES.get(upload.content_type or "")
        if suffix is None:
            raise HTTPException(415, f"Unsupported file type: {upload.content_type}")
        data = await upload.read()
        uri = storage.store_bytes(data, suffix=suffix)
        session.add(Artifact(
            batch_id=batch.id,
            assignment_id=assignment_id,
            image_uri=uri,
            capture_meta={"filename": upload.filename},
        ))
    session.flush()
    # Commit before the worker thread starts reading these rows.
    session.commit()

    get_queue().enqueue("process_batch", {"batch_id": batch.id})
    return batch


@router.get("/batches/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: str, session: Session = Depends(get_session)):
    batch = session.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "Unknown batch")
    return batch


@router.get("/batches/{batch_id}/artifacts", response_model=list[ArtifactOut])
def list_batch_artifacts(batch_id: str, session: Session = Depends(get_session)):
    if session.get(Batch, batch_id) is None:
        raise HTTPException(404, "Unknown batch")
    return session.query(Artifact).filter(Artifact.batch_id == batch_id).all()


@router.get("/artifacts/{artifact_id}", response_model=ArtifactDetail)
def get_artifact(artifact_id: str, session: Session = Depends(get_session)):
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(404, "Unknown artifact")
    return artifact


@router.get("/artifacts/{artifact_id}/extractions", response_model=list[ExtractionOut])
def artifact_extractions(artifact_id: str, session: Session = Depends(get_session)):
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(404, "Unknown artifact")
    out = []
    for region in artifact.regions:
        out.extend(region.extractions)
    return out
