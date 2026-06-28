from datetime import datetime
from app.extensions import db, bcrypt

ROLE_LECTURER = "lecturer"
ROLE_HOD = "hod"
ROLE_DEAN = "dean"
ROLE_QA = "qa_officer"
ROLE_ADMIN = "admin"

ALL_ROLES = [ROLE_LECTURER, ROLE_HOD, ROLE_DEAN, ROLE_QA, ROLE_ADMIN]

ROLE_LABELS = {
    ROLE_LECTURER: "Lecturer",
    ROLE_HOD: "Head of Department",
    ROLE_DEAN: "Dean / Faculty Officer",
    ROLE_QA: "Quality Assurance Officer",
    ROLE_ADMIN: "System Administrator",
}


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)

    faculty_id = db.Column(db.Integer, db.ForeignKey("faculties.id"), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)

    faculty = db.relationship("Faculty", foreign_keys=[faculty_id])
    department = db.relationship("Department", foreign_keys=[department_id])

    def set_password(self, raw_password):
        self.password_hash = bcrypt.generate_password_hash(raw_password).decode("utf-8")

    def check_password(self, raw_password):
        return bcrypt.check_password_hash(self.password_hash, raw_password)

    @property
    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role)

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role,
            "role_label": self.role_label,
            "faculty_id": self.faculty_id,
            "department_id": self.department_id,
            "is_active": self.is_active,
        }

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > datetime.utcnow()
