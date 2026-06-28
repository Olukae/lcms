from flask import Blueprint, render_template
from app.auth.decorators import role_required, get_current_user
from app.models.user import ROLE_HOD
from app.models.curriculum import Curriculum, STATUS_DEPT_REVIEW
from app.models.academic import Course, Programme
from app.services import notification_service

bp = Blueprint("dashboard_hod", __name__, url_prefix="/dashboard/hod")


@bp.route("", methods=["GET"])
@role_required(ROLE_HOD)
def index():
    user = get_current_user()

    # Scope query to the HOD's own department — never trust role alone.
    pending = (
        Curriculum.query.join(Course, Curriculum.course_id == Course.id)
        .join(Programme, Course.programme_id == Programme.id)
        .filter(Programme.department_id == user.department_id)
        .filter(Curriculum.status == STATUS_DEPT_REVIEW)
        .order_by(Curriculum.submitted_at)
        .all()
    )

    return render_template(
        "dashboards/hod.html",
        user=user,
        pending=pending,
        unread_count=notification_service.unread_count(user),
    )
