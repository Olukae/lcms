"""
Seeds the database with a minimal but coherent demo dataset: one faculty,
one department, one programme, one course, and one user per role, so the
five-role workflow can be exercised end-to-end immediately after setup.

Usage:
    flask --app run.py shell -c "from seed import run; run()"
or simply:
    python seed.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models.user import User, ROLE_LECTURER, ROLE_HOD, ROLE_DEAN, ROLE_QA, ROLE_ADMIN
from app.models.academic import Faculty, Department, Programme, Course
from app.models.workflow import WorkflowStage

DEMO_PASSWORD = "Password123!"


def run():
    app = create_app()
    with app.app_context():
        db.create_all()

        if Faculty.query.first():
            print("Database already seeded — skipping. Drop tables first to reseed.")
            return

        faculty = Faculty(name="Faculty of Science", code="SCI")
        db.session.add(faculty)
        db.session.flush()

        department = Department(faculty_id=faculty.id, name="Department of Computer Science", code="CSC")
        db.session.add(department)
        db.session.flush()

        programme = Programme(
            department_id=department.id, name="B.Sc. Computer Science",
            degree_type="B.Sc.", nuc_code="NUC-CSC-001",
        )
        db.session.add(programme)
        db.session.flush()

        course = Course(
            programme_id=programme.id, course_code="CSC301",
            course_title="Data Structures and Algorithms",
            credit_units=3, level="300", semester="First",
        )
        db.session.add(course)

        stages = [
            WorkflowStage(name="Departmental Review", sequence_order=1, role_required=ROLE_HOD),
            WorkflowStage(name="Faculty Board", sequence_order=2, role_required=ROLE_DEAN),
            WorkflowStage(name="Quality Assurance", sequence_order=3, role_required=ROLE_QA),
            WorkflowStage(name="Senate", sequence_order=4, role_required=ROLE_ADMIN),
        ]
        db.session.add_all(stages)

        users = [
            User(full_name="Dr. Ade Lecturer", email="lecturer@lasu.edu.ng",
                 role=ROLE_LECTURER, department_id=department.id),
            User(full_name="Prof. Bisi HOD", email="hod@lasu.edu.ng",
                 role=ROLE_HOD, department_id=department.id, faculty_id=faculty.id),
            User(full_name="Prof. Chika Dean", email="dean@lasu.edu.ng",
                 role=ROLE_DEAN, faculty_id=faculty.id),
            User(full_name="Mrs. Dupe QA", email="qa@lasu.edu.ng", role=ROLE_QA),
            User(full_name="Mr. Emeka Admin", email="admin@lasu.edu.ng", role=ROLE_ADMIN),
        ]
        for u in users:
            u.set_password(DEMO_PASSWORD)
        db.session.add_all(users)

        db.session.commit()

        print("Seed complete. Demo accounts (all use password: %s)" % DEMO_PASSWORD)
        for u in users:
            print(f"  {u.role:12s} {u.email}")


if __name__ == "__main__":
    run()
