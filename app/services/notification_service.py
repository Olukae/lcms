from flask import current_app
from flask_mail import Message
from app.extensions import db, mail
from app.models.audit import Notification


def notify(recipient, message, curriculum=None, send_email=False):
    """Creates an in-app Notification row. Email is optional/stretch per the
    spec — if SMTP isn't configured (MAIL_SUPPRESS_SEND is True), this
    silently skips the email send and only writes the in-app row, so the
    core workflow never blocks on mail configuration.
    """
    note = Notification(
        recipient_user_id=recipient.id,
        curriculum_id=curriculum.id if curriculum else None,
        message=message,
    )
    db.session.add(note)
    db.session.commit()

    if send_email and not current_app.config.get("MAIL_SUPPRESS_SEND", True):
        try:
            msg = Message(
                subject="LCMS Notification",
                recipients=[recipient.email],
                body=message,
            )
            mail.send(msg)
        except Exception as exc:  # pragma: no cover - network/SMTP dependent
            current_app.logger.warning("Email notification failed: %s", exc)

    return note


def unread_count(user):
    return Notification.query.filter_by(recipient_user_id=user.id, is_read=False).count()


def mark_read(notification_id, user):
    note = Notification.query.filter_by(id=notification_id, recipient_user_id=user.id).first()
    if note and not note.is_read:
        note.is_read = True
        db.session.commit()
    return note


def mark_all_read(user):
    Notification.query.filter_by(recipient_user_id=user.id, is_read=False).update(
        {"is_read": True}
    )
    db.session.commit()
