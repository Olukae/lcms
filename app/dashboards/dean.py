from flask import Blueprint, render_template
from app.auth.decorators import role_required, get_current_user
from app.models.user import ROLE_DEAN
from app.models.curriculum import Curriculum, STATUS_FACULTY_REVIEW
from app.models.academic import Course, Programme, Department
from app.services import notification_service

bp = Blueprint("dashboard_dean", __name__, url_prefix="/dashboard/dean")


@bp.route("", methods=["GET"])
@role_required(ROLE_DEAN)
def index():
    user = get_current_user()

    # Scope query to the Dean's own faculty.
    pending = (
        Curriculum.query.join(Course, Curriculum.course_id == Course.id)
        .join(Programme, Course.programme_id == Programme.id)
        .join(Department, Programme.department_id == Department.id)
        .filter(Department.faculty_id == user.faculty_id)
        .filter(Curriculum.status == STATUS_FACULTY_REVIEW)
        .order_by(Curriculum.updated_at)
        .all()
    )

    return render_template(
        "dashboards/dean.html",
        user=user,
        pending=pending,
        unread_count=notification_service.unread_count(user),
    )
