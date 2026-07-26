"""School -> Teacher -> Classroom registration and scoping."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hwportfolio.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _setup(client: TestClient):
    school = client.post("/api/schools", json={"name": "Maple Elementary"}).json()
    teacher = client.post("/api/teachers", json={
        "school_id": school["id"], "display_name": "Ms. Rivera",
        "email": "rivera@maple.example",
    }).json()
    classroom = client.post("/api/classrooms", json={
        "teacher_id": teacher["id"], "name": "Room 12",
        "grade_band": "1", "school_year": "2026-2027",
    }).json()
    return school, teacher, classroom


def test_registration_chain(client):
    school, teacher, classroom = _setup(client)
    assert teacher["school_id"] == school["id"]
    assert classroom["teacher_id"] == teacher["id"]
    assert client.get(f"/api/classrooms/{classroom['id']}").json()["name"] == "Room 12"

    # School registration is idempotent by name; teacher by email.
    again = client.post("/api/schools", json={"name": "Maple Elementary"}).json()
    assert again["id"] == school["id"]
    same_teacher = client.post("/api/teachers", json={
        "school_id": school["id"], "display_name": "M. Rivera",
        "email": "RIVERA@maple.example",
    }).json()
    assert same_teacher["id"] == teacher["id"]


def test_teacher_email_conflict_across_schools(client):
    school, teacher, _ = _setup(client)
    other = client.post("/api/schools", json={"name": "Oak Elementary"}).json()
    response = client.post("/api/teachers", json={
        "school_id": other["id"], "display_name": "Ms. Rivera",
        "email": teacher["email"],
    })
    assert response.status_code == 409


def test_students_and_assignments_scoped_to_classroom(client):
    _, teacher, room_a = _setup(client)
    room_b = client.post("/api/classrooms", json={
        "teacher_id": teacher["id"], "name": "Room 13",
        "grade_band": "2", "school_year": "2026-2027",
    }).json()

    client.post("/api/students", json={
        "external_id": "A1", "display_name": "Ana", "grade_band": "1",
        "school_year": "2026-2027", "classroom_id": room_a["id"],
    })
    client.post("/api/students", json={
        "external_id": "B1", "display_name": "Ben", "grade_band": "2",
        "school_year": "2026-2027", "classroom_id": room_b["id"],
    })

    names_a = [s["display_name"] for s in
               client.get(f"/api/students?classroom_id={room_a['id']}").json()]
    assert names_a == ["Ana"]
    assert len(client.get("/api/students").json()) == 2  # unscoped still lists all

    client.post("/api/assignments", json={"title": "Journal", "classroom_id": room_a["id"]})
    client.post("/api/assignments", json={"title": "Math", "classroom_id": room_b["id"]})
    titles_b = [a["title"] for a in
                client.get(f"/api/assignments?classroom_id={room_b['id']}").json()]
    assert titles_b == ["Math"]


def test_classroom_validation(client):
    response = client.post("/api/students", json={
        "external_id": "X1", "display_name": "X", "grade_band": "1",
        "school_year": "2026-2027", "classroom_id": "nope",
    })
    assert response.status_code == 404
    response = client.post("/api/classrooms", json={
        "teacher_id": "nope", "name": "Room", "grade_band": "1",
        "school_year": "2026-2027",
    })
    assert response.status_code == 404
