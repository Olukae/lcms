from flask import request
from app.extensions import db
from app.models.audit import AuditLog


def log(user, action_type, entity_type, entity_id=None, description=None):
    """Writes a single append-only audit log row. Called from every
    state-changing operation: logins, approvals, returns, record edits,
    admin actions. This function never updates or deletes existing rows.

    `user` may be None for system-initiated events.
    """
    ip = None
    try:
        if request:
            ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            if ip and "," in ip:
                ip = ip.split(",")[0].strip()
    except RuntimeError:
        # Outside of request context (e.g. CLI seed script)
        ip = None

    entry = AuditLog(
        user_id=user.id if user else None,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        ip_address=ip,
    )
    db.session.add(entry)
    db.session.commit()
    return entry
