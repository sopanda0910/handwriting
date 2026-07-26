"""End-to-end API flow: roster -> batch upload -> pipeline -> review commit ->
timeline -> parent share. Also exercises the structural constraints:
teacher-in-the-loop, supersede-not-delete, share expiry + audit log.
"""

from __future__ import annotations

import time
from datetime import timedelta

import cv2
import pytest
from fastapi.testclient import TestClient

from hwportfolio.db import session_scope
from hwportfolio.main import app
from hwportfolio.models import Extraction, ReviewState, ShareGrant, TimelineEntry, utcnow
from hwportfolio.pipeline.deskew import deskew
from hwportfolio.pipeline.segment import segment
from hwportfolio.transcribe.mock import MockProvider

from .synth import add_qr, add_rules, blank_page, gray, write_lines

VERBATIM = "I wnt to the stor"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _page_with_qr(external_id: str) -> bytes:
    page = blank_page()
    add_rules(page)
    write_lines(page, [VERBATIM])
    add_qr(page, f"hwp:v1:{external_id}")

    # Register mock ground truth for the region crop the pipeline will cut.
    result = deskew(page)
    seg = segment(gray(result.image))
    for r in seg.regions:
        crop = result.image[r["y"]:r["y"] + r["h"], r["x"]:r["x"] + r["w"]]
        MockProvider.register_ground_truth(crop, VERBATIM)

    ok, buffer = cv2.imencode(".png", page)
    assert ok
    return buffer.tobytes()


def _wait_batch(client: TestClient, batch_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        batch = client.get(f"/api/batches/{batch_id}").json()
        if batch["status"] in ("ready_for_review", "failed"):
            return batch
        time.sleep(0.2)
    raise TimeoutError("Batch did not finish processing")


def test_full_flow(client):
    # Roster
    student = client.post("/api/students", json={
        "external_id": "S001", "display_name": "Maya R.",
        "grade_band": "1", "school_year": "2026-2027",
    }).json()
    assignment = client.post("/api/assignments", json={"title": "Journal — July"}).json()

    # QR label renders
    qr = client.get(f"/api/students/{student['id']}/qr.png")
    assert qr.status_code == 200 and qr.headers["content-type"] == "image/png"

    # Batch upload -> async pipeline
    page_bytes = _page_with_qr("S001")
    response = client.post(
        f"/api/assignments/{assignment['id']}/batches",
        files=[("files", ("page1.png", page_bytes, "image/png"))],
    )
    assert response.status_code == 200, response.text
    batch = _wait_batch(client, response.json()["id"])
    assert batch["status"] == "ready_for_review", batch.get("error")

    # Artifact matched to the student via QR
    artifacts = client.get(f"/api/batches/{batch['id']}/artifacts").json()
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact["student_id"] == student["id"]
    assert artifact["student_match_method"] == "qr"
    assert artifact["ruled_paper"] is True

    # Extractions are provisional; verbatim preserved
    extractions = client.get(f"/api/artifacts/{artifact['id']}/extractions").json()
    real = [e for e in extractions if e["verbatim"]]
    assert real and real[0]["state"] == "provisional"
    assert real[0]["verbatim"] == VERBATIM

    # Timeline is EMPTY before any commit — teacher-in-the-loop is structural.
    timeline = client.get(f"/api/students/{student['id']}/timeline").json()
    assert timeline == []

    # Teacher commits the extraction
    committed = client.post(f"/api/review/extractions/{real[0]['id']}/commit")
    assert committed.status_code == 200, committed.text
    timeline = client.get(f"/api/students/{student['id']}/timeline").json()
    assert len(timeline) == 1
    assert VERBATIM.split()[1] in timeline[0]["summary"]  # "wnt" survives to the record

    # Double-commit is rejected
    assert client.post(f"/api/review/extractions/{real[0]['id']}/commit").status_code == 400

    # Observations exist with bboxes; commit one
    detail = client.get(f"/api/artifacts/{artifact['id']}").json()
    provisional_obs = [o for o in detail["observations"] if o["state"] == "provisional"]
    assert provisional_obs, "Pipeline produced no committable observations"
    obs = provisional_obs[0]
    assert obs["w"] > 0 and obs["h"] > 0
    assert client.post(f"/api/review/observations/{obs['id']}/commit").status_code == 200

    # Parent share: curated, expiring, audited
    entry_ids = [e["id"] for e in client.get(f"/api/students/{student['id']}/timeline").json()]
    grant = client.post("/api/shares", json={
        "student_id": student["id"],
        "included_entry_ids": entry_ids[:1],
        "note": "Maya's spacing ratio improved from 1.2 to 2.0 since June.",
    }).json()
    view = client.get(f"/api/shared/{grant['token']}")
    assert view.status_code == 200
    assert view.json()["student_name"] == "Maya R."
    assert len(view.json()["entries"]) == 1

    log = client.get(f"/api/shares/{grant['id']}/access-log").json()
    assert len(log) == 1  # every read is audited

    # Revocation closes the link
    client.post(f"/api/shares/{grant['id']}/revoke")
    assert client.get(f"/api/shared/{grant['token']}").status_code == 410


def test_share_note_language_lint(client):
    student = client.post("/api/students", json={
        "external_id": "S002", "display_name": "Ben K.",
        "grade_band": "K", "school_year": "2026-2027",
    }).json()
    response = client.post("/api/shares", json={
        "student_id": student["id"],
        "included_entry_ids": [],
        "note": "Ben shows signs of dysgraphia and should be evaluated.",
    })
    assert response.status_code == 422
    assert "observational-language" in response.json()["detail"]


def test_share_expiry(client):
    student = client.post("/api/students", json={
        "external_id": "S003", "display_name": "Ana L.",
        "grade_band": "2", "school_year": "2026-2027",
    }).json()
    grant = client.post("/api/shares", json={
        "student_id": student["id"], "included_entry_ids": [],
    }).json()
    with session_scope() as session:
        row = session.get(ShareGrant, grant["id"])
        row.expires_at = utcnow() - timedelta(hours=1)
    assert client.get(f"/api/shared/{grant['token']}").status_code == 410


def test_teacher_correction_supersedes(client):
    """Nothing is deleted, only superseded (GOALS §6)."""
    student = client.post("/api/students", json={
        "external_id": "S004", "display_name": "Kai T.",
        "grade_band": "1", "school_year": "2026-2027",
    }).json()
    assignment = client.post("/api/assignments", json={"title": "t"}).json()
    page_bytes = _page_with_qr("S004")
    response = client.post(
        f"/api/assignments/{assignment['id']}/batches",
        files=[("files", ("p.png", page_bytes, "image/png"))],
    )
    _wait_batch(client, response.json()["id"])
    artifacts = client.get(f"/api/batches/{response.json()['id']}/artifacts").json()
    extractions = client.get(f"/api/artifacts/{artifacts[0]['id']}/extractions").json()
    original = next(e for e in extractions if e["verbatim"])

    corrected = client.post(
        f"/api/review/extractions/{original['id']}/correct",
        json={"verbatim": "I wnt to the store"},
    ).json()
    assert corrected["supersedes_id"] == original["id"]
    assert corrected["source"] == "teacher"

    with session_scope() as session:
        old = session.get(Extraction, original["id"])
        assert old is not None                      # never deleted
        assert old.state == ReviewState.superseded  # only superseded
        assert old.verbatim == VERBATIM             # original preserved

    # Committing the correction lands the corrected text on the timeline
    assert client.post(f"/api/review/extractions/{corrected['id']}/commit").status_code == 200
    timeline = client.get(f"/api/students/{student['id']}/timeline").json()
    assert any("store" in e["payload"].get("verbatim", "") for e in timeline)


def test_commit_requires_student_match(client):
    """A page with no roster match cannot reach any timeline (GOALS C4)."""
    assignment = client.post("/api/assignments", json={"title": "t"}).json()
    page = blank_page()
    write_lines(page, ["hello"])  # no QR
    result = deskew(page)
    seg = segment(gray(result.image))
    for r in seg.regions:
        crop = result.image[r["y"]:r["y"] + r["h"], r["x"]:r["x"] + r["w"]]
        MockProvider.register_ground_truth(crop, "hello")
    ok, buffer = cv2.imencode(".png", page)
    response = client.post(
        f"/api/assignments/{assignment['id']}/batches",
        files=[("files", ("p.png", buffer.tobytes(), "image/png"))],
    )
    _wait_batch(client, response.json()["id"])
    artifacts = client.get(f"/api/batches/{response.json()['id']}/artifacts").json()
    assert artifacts[0]["student_id"] is None
    extractions = client.get(f"/api/artifacts/{artifacts[0]['id']}/extractions").json()
    target = next(e for e in extractions if e["verbatim"])
    response = client.post(f"/api/review/extractions/{target['id']}/commit")
    assert response.status_code == 400
    assert "assign a student" in response.json()["detail"].lower()
