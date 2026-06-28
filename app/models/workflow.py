from datetime import datetime
from app.extensions import db

DECISION_APPROVED = "approved"
DECISION_RETURNED = "returned"
DECISION_REFERRED = "referred"


class WorkflowStage(db.Model):
    __tablename__ = "workflow_stages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Departmental Review / Faculty Board / Quality Assurance / Senate
    sequence_order = db.Column(db.Integer, nullable=False)  # 1-4
    role_required = db.Column(db.String(20), nullable=False)  # role that acts at this stage

    def __repr__(self):
        return f"<WorkflowStage {self.sequence_order}:{self.name}>"


class ApprovalAction(db.Model):
    __tablename__ = "approval_actions"

    id = db.Column(db.Integer, primary_key=True)
    curriculum_id = db.Column(db.Integer, db.ForeignKey("curricula.id"), nullable=False)
    workflow_stage_id = db.Column(db.Integer, db.ForeignKey("workflow_stages.id"), nullable=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    decision = db.Column(db.String(20), nullable=False)  # approved / returned / referred
    comments = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    workflow_stage = db.relationship("WorkflowStage", foreign_keys=[workflow_stage_id])
    actor = db.relationship("User", foreign_keys=[actor_user_id])

    def __repr__(self):
        return f"<ApprovalAction curr={self.curriculum_id} {self.decision}>"
