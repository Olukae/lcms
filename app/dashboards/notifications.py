from flask import Blueprint, jsonify
from app.auth.decorators import login_required, get_current_user
from app.models.audit import Notification
from app.services import notification_service

bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@bp.route("", methods=["GET"])
@login_required
def list_notifications():
    user = get_current_user()
    items = Notification.query.filter_by(recipient_user_id=user.id).order_by(
        Notification.created_at.desc()
    ).limit(50).all()
    return jsonify({
        "notifications": [
            {
                "id": n.id, "message": n.message, "is_read": n.is_read,
                "curriculum_id": n.curriculum_id, "created_at": n.created_at.isoformat(),
            } for n in items
        ],
        "unread_count": notification_service.unread_count(user),
    }), 200


@bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    user = get_current_user()
    note = notification_service.mark_read(notification_id, user)
    if note is None:
        return jsonify({"error": "Notification not found."}), 404
    return jsonify({"message": "marked read"}), 200


@bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read():
    user = get_current_user()
    notification_service.mark_all_read(user)
    return jsonify({"message": "all marked read"}), 200
