from datetime import datetime
from app.extensions import db


class Faculty(db.Model):
    __tablename__ = "faculties"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    departments = db.relationship("Department", backref="faculty", lazy="dynamic",
                                   foreign_keys="Department.faculty_id")

    def __repr__(self):
        return f"<Faculty {self.code}>"


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculties.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(20), nullable=False)

    programmes = db.relationship("Programme", backref="department", lazy="dynamic",
                                  foreign_keys="Programme.department_id")

    def __repr__(self):
        return f"<Department {self.code}>"


class Programme(db.Model):
    __tablename__ = "programmes"

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    degree_type = db.Column(db.String(50), nullable=False)  # e.g. B.Sc, B.A, HND
    nuc_code = db.Column(db.String(30), nullable=True)

    courses = db.relationship("Course", backref="programme", lazy="dynamic",
                               foreign_keys="Course.programme_id")

    def __repr__(self):
        return f"<Programme {self.name}>"


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    programme_id = db.Column(db.Integer, db.ForeignKey("programmes.id"), nullable=False)
    course_code = db.Column(db.String(20), nullable=False)
    course_title = db.Column(db.String(200), nullable=False)
    credit_units = db.Column(db.Integer, nullable=False)
    level = db.Column(db.String(10), nullable=True)      # e.g. "300"
    semester = db.Column(db.String(20), nullable=True)    # e.g. "First", "Second"

    def __repr__(self):
        return f"<Course {self.course_code}>"
