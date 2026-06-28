from flask import Blueprint, render_template, jsonify
from app.auth.decorators import role_required, get_current_user
from app.models.user import ROLE_LECTURER
from app.models.curriculum import Curriculum, STATUS_RETURNED
from app.services import notification_service

bp = Blueprint("dashboard_lecturer", __name__, url_prefix="/dashboard/lecturer")


@bp.route("", methods=["GET"])
@role_required(ROLE_LECTURER)
def index():
    user = get_current_user()
    curricula = Curriculum.query.filter_by(originating_user_id=user.id).order_by(
        Curriculum.updated_at.desc()
    ).all()

    needs_revision = [c for c in curricula if c.status == STATUS_RETURNED]

    return render_template(
        "dashboards/lecturer.html",
        user=user,
        curricula=curricula,
        needs_revision_count=len(needs_revision),
        unread_count=notification_service.unread_count(user),
    )
