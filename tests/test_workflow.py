from app.models.user import ROLE_LECTURER, ROLE_HOD, ROLE_DEAN, ROLE_QA, ROLE_ADMIN
from tests.conftest import login


def _create_draft(client, org):
    resp = client.post("/api/curriculum", json={
        "programme_id": org["programme_id"], "course_code": "CSC301",
        "course_title": "Data Structures", "credit_units": 3,
        "level": "300", "semester": "First",
        "course_description": "Intro.", "learning_outcomes": "Outcomes.",
        "reading_list": "CLRS.", "assessment_breakdown": {"CA": 30, "Exam": 70},
    })
    assert resp.status_code == 201
    return resp.get_json()["curriculum"]["id"]


def test_full_approval_pipeline(client, users, org):
    login(client, ROLE_LECTURER)
    cid = _create_draft(client, org)

    resp = client.post(f"/api/curriculum/{cid}/submit")
    assert resp.status_code == 200
    assert resp.get_json()["curriculum"]["status"] == "dept_review"
    client.post("/api/auth/logout")

    for role, expected_next in [
        (ROLE_HOD, "faculty_review"),
        (ROLE_DEAN, "qa_review"),
        (ROLE_QA, "senate_review"),
    ]:
        login(client, role)
        resp = client.post(f"/api/curriculum/{cid}/decision", json={"decision": "approved"})
        assert resp.status_code == 200
        assert resp.get_json()["curriculum"]["status"] == expected_next
        client.post("/api/auth/logout")

    login(client, ROLE_ADMIN)
    resp = client.post(f"/dashboard/admin/senate/{cid}/ratify", json={"decision": "approved"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "approved"


def test_return_sends_back_to_lecturer(client, users, org):
    login(client, ROLE_LECTURER)
    cid = _create_draft(client, org)
    client.post(f"/api/curriculum/{cid}/submit")
    client.post("/api/auth/logout")

    login(client, ROLE_HOD)
    resp = client.post(f"/api/curriculum/{cid}/decision", json={
        "decision": "returned", "comments": "Please revise outcomes.",
    })
    assert resp.status_code == 200
    assert resp.get_json()["curriculum"]["status"] == "returned"
    client.post("/api/auth/logout")

    login(client, ROLE_LECTURER)
    resp = client.get(f"/api/curriculum/{cid}")
    assert resp.get_json()["curriculum"]["last_return_comment"] == "Please revise outcomes."


def test_return_requires_comment(client, users, org):
    login(client, ROLE_LECTURER)
    cid = _create_draft(client, org)
    client.post(f"/api/curriculum/{cid}/submit")
    client.post("/api/auth/logout")

    login(client, ROLE_HOD)
    resp = client.post(f"/api/curriculum/{cid}/decision", json={"decision": "returned"})
    assert resp.status_code == 400


def test_wrong_role_cannot_act_at_stage(client, users, org):
    login(client, ROLE_LECTURER)
    cid = _create_draft(client, org)
    client.post(f"/api/curriculum/{cid}/submit")
    client.post("/api/auth/logout")

    # Dean tries to act while it's still at dept_review (HOD's stage)
    login(client, ROLE_DEAN)
    resp = client.post(f"/api/curriculum/{cid}/decision", json={"decision": "approved"})
    assert resp.status_code == 409


def test_only_originating_lecturer_can_submit(client, app, users, org):
    from app.extensions import db
    from app.models.user import User

    with app.app_context():
        other = User(full_name="Other Lecturer", email="other@test.com", role=ROLE_LECTURER,
                     department_id=org["department_id"])
        other.set_password("Password123!")
        db.session.add(other)
        db.session.commit()

    login(client, ROLE_LECTURER)
    cid = _create_draft(client, org)
    client.post("/api/auth/logout")

    client.post("/api/auth/login", json={"email": "other@test.com", "password": "Password123!"})
    resp = client.post(f"/api/curriculum/{cid}/submit")
    assert resp.status_code == 409


def test_cannot_submit_already_submitted_curriculum(client, users, org):
    login(client, ROLE_LECTURER)
    cid = _create_draft(client, org)
    client.post(f"/api/curriculum/{cid}/submit")

    resp = client.post(f"/api/curriculum/{cid}/submit")
    assert resp.status_code == 409


def test_version_numbers_increment_correctly(client, users, org):
    login(client, ROLE_LECTURER)
    cid = _create_draft(client, org)
    client.post(f"/api/curriculum/{cid}/submit")
    client.post("/api/auth/logout")

    for role in [ROLE_HOD, ROLE_DEAN, ROLE_QA]:
        login(client, role)
        client.post(f"/api/curriculum/{cid}/decision", json={"decision": "approved"})
        client.post("/api/auth/logout")

    login(client, ROLE_ADMIN)
    client.post(f"/dashboard/admin/senate/{cid}/ratify", json={"decision": "approved"})

    resp = client.get(f"/api/curriculum/{cid}/history")
    versions = resp.get_json()["versions"]
    version_numbers = [v["version_no"] for v in versions]
    assert version_numbers == sorted(set(version_numbers)), "version numbers must be unique and increasing"
    assert version_numbers == list(range(1, len(versions) + 1))


def test_hod_from_wrong_department_cannot_decide(client, app, users, org):
    from app.extensions import db
    from app.models.user import User
    from app.models.academic import Faculty, Department

    with app.app_context():
        other_faculty = Faculty(name="Other Faculty", code="OTH")
        db.session.add(other_faculty)
        db.session.flush()
        other_dept = Department(faculty_id=other_faculty.id, name="Other Dept", code="OTD")
        db.session.add(other_dept)
        db.session.flush()
        wrong_hod = User(full_name="Wrong HOD", email="wronghod@test.com", role=ROLE_HOD,
                          department_id=other_dept.id, faculty_id=other_faculty.id)
        wrong_hod.set_password("Password123!")
        db.session.add(wrong_hod)
        db.session.commit()

    login(client, ROLE_LECTURER)
    cid = _create_draft(client, org)
    client.post(f"/api/curriculum/{cid}/submit")
    client.post("/api/auth/logout")

    client.post("/api/auth/login", json={"email": "wronghod@test.com", "password": "Password123!"})
    resp = client.post(f"/api/curriculum/{cid}/decision", json={"decision": "approved"})
    assert resp.status_code == 409
