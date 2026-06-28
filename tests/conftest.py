import pytest
from app import create_app
from app.extensions import db
from app.models.user import User, ROLE_LECTURER, ROLE_HOD, ROLE_DEAN, ROLE_QA, ROLE_ADMIN
from app.models.academic import Faculty, Department, Programme, Course

DEMO_PASSWORD = "Password123!"


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def org(app):
    with app.app_context():
        faculty = Faculty(name="Faculty of Science", code="SCI")
        db.session.add(faculty)
        db.session.flush()
        department = Department(faculty_id=faculty.id, name="Computer Science", code="CSC")
        db.session.add(department)
        db.session.flush()
        programme = Programme(department_id=department.id, name="B.Sc. CS", degree_type="B.Sc.")
        db.session.add(programme)
        db.session.flush()
        course = Course(programme_id=programme.id, course_code="CSC301",
                         course_title="Data Structures", credit_units=3,
                         level="300", semester="First")
        db.session.add(course)
        db.session.commit()
        return {
            "faculty_id": faculty.id,
            "department_id": department.id,
            "programme_id": programme.id,
            "course_id": course.id,
        }


@pytest.fixture
def users(app, org):
    with app.app_context():
        accounts = {}
        specs = [
            (ROLE_LECTURER, org["department_id"], None),
            (ROLE_HOD, org["department_id"], org["faculty_id"]),
            (ROLE_DEAN, None, org["faculty_id"]),
            (ROLE_QA, None, None),
            (ROLE_ADMIN, None, None),
        ]
        for role, dept, fac in specs:
            u = User(full_name=f"Test {role}", email=f"{role}@test.com", role=role,
                     department_id=dept, faculty_id=fac)
            u.set_password(DEMO_PASSWORD)
            db.session.add(u)
            db.session.flush()
            accounts[role] = u.id
        db.session.commit()
        return accounts


def login(client, role):
    return client.post("/api/auth/login", json={
        "email": f"{role}@test.com", "password": DEMO_PASSWORD,
    })
