from app.models.user import ROLE_LECTURER
from tests.conftest import login


def test_create_curriculum_requires_fields(client, users, org):
    login(client, ROLE_LECTURER)
    resp = client.post("/api/curriculum", json={"programme_id": org["programme_id"]})
    assert resp.status_code == 400


def test_autosave_does_not_create_version(client, users, org):
    login(client, ROLE_LECTURER)
    resp = client.post("/api/curriculum", json={
        "programme_id": org["programme_id"], "course_code": "CSC301",
        "course_title": "Data Structures", "credit_units": 3,
        "course_description": "x", "learning_outcomes": "y", "reading_list": "z",
    })
    cid = resp.get_json()["curriculum"]["id"]

    for i in range(3):
        resp = client.patch(f"/api/curriculum/{cid}/autosave", json={"draft_data": {"note": i}})
        assert resp.status_code == 200

    resp = client.get(f"/api/curriculum/{cid}/history")
    assert resp.get_json()["versions"] == []


def test_edit_blocked_once_in_review(client, users, org):
    login(client, ROLE_LECTURER)
    resp = client.post("/api/curriculum", json={
        "programme_id": org["programme_id"], "course_code": "CSC301",
        "course_title": "Data Structures", "credit_units": 3,
        "course_description": "x", "learning_outcomes": "y", "reading_list": "z",
    })
    cid = resp.get_json()["curriculum"]["id"]
    client.post(f"/api/curriculum/{cid}/submit")

    resp = client.put(f"/api/curriculum/{cid}", json={"course_description": "changed"})
    assert resp.status_code == 409


def test_cannot_edit_others_proposal(client, app, users, org):
    from app.extensions import db
    from app.models.user import User

    with app.app_context():
        other = User(full_name="Other", email="other2@test.com", role=ROLE_LECTURER,
                     department_id=org["department_id"])
        other.set_password("Password123!")
        db.session.add(other)
        db.session.commit()

    login(client, ROLE_LECTURER)
    resp = client.post("/api/curriculum", json={
        "programme_id": org["programme_id"], "course_code": "CSC301",
        "course_title": "Data Structures", "credit_units": 3,
        "course_description": "x", "learning_outcomes": "y", "reading_list": "z",
    })
    cid = resp.get_json()["curriculum"]["id"]
    client.post("/api/auth/logout")

    client.post("/api/auth/login", json={"email": "other2@test.com", "password": "Password123!"})
    resp = client.put(f"/api/curriculum/{cid}", json={"course_description": "hijacked"})
    assert resp.status_code == 403


def test_pdf_export(client, users, org):
    login(client, ROLE_LECTURER)
    resp = client.post("/api/curriculum", json={
        "programme_id": org["programme_id"], "course_code": "CSC301",
        "course_title": "Data Structures", "credit_units": 3,
        "course_description": "x", "learning_outcomes": "y", "reading_list": "z",
    })
    cid = resp.get_json()["curriculum"]["id"]

    resp = client.get(f"/api/curriculum/{cid}/export.pdf")
    assert resp.status_code == 200
    assert resp.content_type == "application/pdf"
    assert len(resp.data) > 100
