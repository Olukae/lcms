import secrets
import hashlib
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, set_access_cookies, unset_jwt_cookies,
    verify_jwt_in_request,
)

from app.extensions import db
from app.models.user import User, PasswordResetToken
from app.services import audit_service, notification_service

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _role_dashboard_path(role):
    return {
        "lecturer": "/dashboard/lecturer",
        "hod": "/dashboard/hod",
        "dean": "/dashboard/dean",
        "qa_officer": "/dashboard/qa",
        "admin": "/dashboard/admin",
    }.get(role, "/")


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    user = User.query.filter(db.func.lower(User.email) == email).first()

    # Constant-shape response regardless of which check fails — avoids
    # leaking whether an email exists in the system.
    if user is None or not user.is_active or not user.check_password(password):
        audit_service.log(
            None, "login_failed", "User", None,
            f"Failed login attempt for email '{email}'."
        )
        return jsonify({"error": "Invalid email or password."}), 401

    user.last_login_at = datetime.utcnow()
    db.session.commit()

    audit_service.log(user, "login_success", "User", user.id, "User logged in.")

    access_token = create_access_token(identity=str(user.id))
    resp = jsonify({
        "message": "Login successful.",
        "user": user.to_dict(),
        "redirect": _role_dashboard_path(user.role),
    })
    set_access_cookies(resp, access_token)
    return resp, 200


@bp.route("/logout", methods=["POST"])
def logout():
    user = None
    try:
        verify_jwt_in_request(optional=True)
        from app.auth.decorators import get_current_user
        user = get_current_user()
    except Exception:
        pass

    resp = jsonify({"message": "Logged out."})
    unset_jwt_cookies(resp)
    if user:
        audit_service.log(user, "logout", "User", user.id, "User logged out.")
    return resp, 200


@bp.route("/password-reset/request", methods=["POST"])
def request_password_reset():
    """Generates a single-use token, stores only its hash, and either emails
    it or (if SMTP isn't configured) returns it directly so the flow is
    testable/usable in environments without mail set up. Always returns a
    generic success message regardless of whether the email exists."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    generic_response = jsonify({
        "message": "If an account with that email exists, a reset link has been generated."
    })

    if not email:
        return jsonify({"error": "Email is required."}), 400

    user = User.query.filter(db.func.lower(User.email) == email).first()
    if user is None or not user.is_active:
        return generic_response, 200

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expiry_minutes = current_app.config.get("PASSWORD_RESET_EXPIRY_MINUTES", 30)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=expiry_minutes),
    )
    db.session.add(reset_token)
    db.session.commit()

    audit_service.log(
        user, "password_reset_requested", "User", user.id,
        "Password reset token generated."
    )

    mail_configured = not current_app.config.get("MAIL_SUPPRESS_SEND", True)
    if mail_configured:
        notification_service.notify(
            user,
            f"A password reset was requested for your LCMS account. "
            f"Use this link within {expiry_minutes} minutes: /reset-password?token={raw_token}",
            send_email=True,
        )
        return generic_response, 200

    # No mail configured: return the token directly so the flow remains usable
    # in dev/demo environments. In production, mail must be configured so
    # this branch is never the means of delivery.
    payload = generic_response.get_json()
    payload["dev_reset_token"] = raw_token
    payload["note"] = "Email is not configured in this environment; token returned directly for development use."
    return jsonify(payload), 200


@bp.route("/password-reset/confirm", methods=["POST"])
def confirm_password_reset():
    data = request.get_json(silent=True) or {}
    raw_token = data.get("token") or ""
    new_password = data.get("password") or ""

    if not raw_token or not new_password:
        return jsonify({"error": "Token and new password are required."}), 400
    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    reset_token = PasswordResetToken.query.filter_by(token_hash=token_hash).first()

    if reset_token is None or not reset_token.is_valid:
        return jsonify({"error": "This reset link is invalid or has expired."}), 400

    user = reset_token.user
    user.set_password(new_password)
    reset_token.used_at = datetime.utcnow()
    db.session.commit()

    audit_service.log(
        user, "password_reset_completed", "User", user.id,
        "Password successfully reset via token."
    )

    return jsonify({"message": "Password has been reset. You may now log in."}), 200


@bp.route("/me", methods=["GET"])
def me():
    verify_jwt_in_request()
    from app.auth.decorators import get_current_user
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Not authenticated."}), 401
    return jsonify({"user": user.to_dict()}), 200
