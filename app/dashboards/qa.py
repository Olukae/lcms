from flask import Blueprint, render_template
from app.auth.decorators import role_required, get_current_user
from app.models.user import ROLE_QA
from app.models.curriculum import Curriculum, STATUS_QA_REVIEW
from app.services import notification_service

bp = Blueprint("dashboard_qa", __name__, url_prefix="/dashboard/qa")


@bp.route("", methods=["GET"])
@role_required(ROLE_QA)
def index():
    user = get_current_user()

    pending = (
        Curriculum.query.filter(Curriculum.status == STATUS_QA_REVIEW)
        .order_by(Curriculum.updated_at)
        .all()
    )

    return render_template(
        "dashboards/qa.html",
        user=user,
        pending=pending,
        unread_count=notification_service.unread_count(user),
    )
