from datetime import datetime
from app.extensions import db

STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_DEPT_REVIEW = "dept_review"
STATUS_FACULTY_REVIEW = "faculty_review"
STATUS_QA_REVIEW = "qa_review"
STATUS_SENATE_REVIEW = "senate_review"
STATUS_APPROVED = "approved"
STATUS_RETURNED = "returned"

# Ordered pipeline used by the workflow engine to determine "next stage".
STATUS_SEQUENCE = [
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    STATUS_DEPT_REVIEW,
    STATUS_FACULTY_REVIEW,
    STATUS_QA_REVIEW,
    STATUS_SENATE_REVIEW,
    STATUS_APPROVED,
]

STATUS_LABELS = {
    STATUS_DRAFT: "Draft",
    STATUS_SUBMITTED: "Submitted",
    STATUS_DEPT_REVIEW: "Departmental Review",
    STATUS_FACULTY_REVIEW: "Faculty Board Review",
    STATUS_QA_REVIEW: "Quality Assurance Review",
    STATUS_SENATE_REVIEW: "Cleared for Senate",
    STATUS_APPROVED: "Approved",
    STATUS_RETURNED: "Returned for Revision",
}


class Curriculum(db.Model):
    __tablename__ = "curricula"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    originating_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    status = db.Column(db.String(20), nullable=False, default=STATUS_DRAFT, index=True)
    current_version_no = db.Column(db.Integer, nullable=False, default=0)

    course_description = db.Column(db.Text, nullable=True)
    learning_outcomes = db.Column(db.Text, nullable=True)
    prerequisites = db.Column(db.Text, nullable=True)
    assessment_breakdown = db.Column(db.JSON, nullable=True)  # e.g. {"CA": 30, "Exam": 70}
    reading_list = db.Column(db.Text, nullable=True)

    draft_data = db.Column(db.JSON, nullable=True)
    last_autosaved_at = db.Column(db.DateTime, nullable=True)

    # Snapshot of the most recent return-for-revision comment, surfaced to the lecturer.
    last_return_comment = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=True)

    course = db.relationship("Course", foreign_keys=[course_id])
    originating_user = db.relationship("User", foreign_keys=[originating_user_id])
    versions = db.relationship(
        "CurriculumVersion", backref="curriculum", lazy="dynamic",
        order_by="CurriculumVersion.version_no", cascade="all, delete-orphan"
    )
    approval_actions = db.relationship(
        "ApprovalAction", backref="curriculum", lazy="dynamic",
        order_by="ApprovalAction.created_at", cascade="all, delete-orphan"
    )

    @property
    def status_label(self):
        return STATUS_LABELS.get(self.status, self.status)

    # Convenience scoping helpers used by routes/services for RBAC query scoping.
    @property
    def department_id(self):
        if self.course and self.course.programme and self.course.programme.department:
            return self.course.programme.department.id
        return None

    @property
    def faculty_id(self):
        if self.course and self.course.programme and self.course.programme.department:
            return self.course.programme.department.faculty_id
        return None

    def field_snapshot(self):
        """Returns the current set of NUC-relevant fields for versioning/diffing."""
        return {
            "course_code": self.course.course_code if self.course else None,
            "course_title": self.course.course_title if self.course else None,
            "credit_units": self.course.credit_units if self.course else None,
            "course_description": self.course_description,
            "learning_outcomes": self.learning_outcomes,
            "prerequisites": self.prerequisites,
            "assessment_breakdown": self.assessment_breakdown,
            "reading_list": self.reading_list,
        }

    def __repr__(self):
        return f"<Curriculum {self.id} status={self.status}>"


class CurriculumVersion(db.Model):
    __tablename__ = "curriculum_versions"

    id = db.Column(db.Integer, primary_key=True)
    curriculum_id = db.Column(db.Integer, db.ForeignKey("curricula.id"), nullable=False)
    version_no = db.Column(db.Integer, nullable=False)
    snapshot_data = db.Column(db.JSON, nullable=False)
    changed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approval_action_id = db.Column(db.Integer, db.ForeignKey("approval_actions.id"), nullable=True)
    change_summary = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    changed_by = db.relationship("User", foreign_keys=[changed_by_user_id])

    def __repr__(self):
        return f"<CurriculumVersion curr={self.curriculum_id} v{self.version_no}>"
