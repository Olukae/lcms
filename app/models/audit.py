from datetime import datetime
from app.extensions import db


class AuditLog(db.Model):
    """Append-only audit trail. No route, service, or admin action may UPDATE or
    DELETE rows in this table. In production, additionally enforce this at the
    database grant level (REVOKE UPDATE, DELETE ON audit_logs FROM lcms_user;)."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # null = system event
    action_type = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<AuditLog {self.action_type} {self.entity_type}#{self.entity_id}>"


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    curriculum_id = db.Column(db.Integer, db.ForeignKey("curricula.id"), nullable=True)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    recipient = db.relationship("User", foreign_keys=[recipient_user_id])
    curriculum = db.relationship("Curriculum", foreign_keys=[curriculum_id])

    def __repr__(self):
        return f"<Notification to={self.recipient_user_id} read={self.is_read}>"
