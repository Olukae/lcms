from flask import Blueprint, render_template, redirect
from flask_jwt_extended import verify_jwt_in_request
from app.auth.decorators import get_current_user

bp = Blueprint("views", __name__)

_DASHBOARD_PATHS = {
    "lecturer": "/dashboard/lecturer",
    "hod": "/dashboard/hod",
    "dean": "/dashboard/dean",
    "qa_officer": "/dashboard/qa",
    "admin": "/dashboard/admin",
}

def _get_authenticated_user():
    """Returns user if JWT valid, else None."""
    try:
        verify_jwt_in_request()
        return get_current_user()
    except Exception:
        return None

@bp.route("/login", methods=["GET"])
def login_page():
    try:
        verify_jwt_in_request(optional=True)
        user = get_current_user()
        if user:
            return redirect(_DASHBOARD_PATHS.get(user.role, "/login"))
    except Exception:
        pass
    return render_template("auth/login.html")

@bp.route("/reset-password", methods=["GET"])
def reset_password_page():
    return render_template("auth/reset_password.html")

@bp.route("/forgot-password", methods=["GET"])
def forgot_password_page():
    return render_template("auth/forgot_password.html")

@bp.route("/curriculum/<int:curriculum_id>", methods=["GET"])
def curriculum_detail_page(curriculum_id):
    user = _get_authenticated_user()
    if not user:
        return redirect("/login")
    return render_template("curriculum/detail.html", curriculum_id=curriculum_id, user=user)

@bp.route("/curriculum/<int:curriculum_id>/edit", methods=["GET"])
def curriculum_edit_page(curriculum_id):
    user = _get_authenticated_user()
    if not user:
        return redirect("/login")
    return render_template("curriculum/edit.html", curriculum_id=curriculum_id, user=user)

@bp.route("/curriculum/new", methods=["GET"])
def curriculum_new_page():
    user = _get_authenticated_user()
    if not user:
        return redirect("/login")
    return render_template("curriculum/new.html", user=user)

@bp.route("/reports", methods=["GET"])
def reports_page():
    user = _get_authenticated_user()
    if not user:
        return redirect("/login")
    return render_template("reports/index.html", user=user)
