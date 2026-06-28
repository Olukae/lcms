from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.models.user import User


def get_current_user():
    """Call only after verify_jwt_in_request() (or inside a route already
    guarded by @jwt_required-style decorators below)."""
    user_id = get_jwt_identity()
    if user_id is None:
        return None
    return User.query.get(int(user_id))


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = get_current_user()
        if user is None or not user.is_active:
            return jsonify({"error": "Authentication required."}), 401
        return fn(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """Usage: @role_required('hod') or @role_required('hod', 'dean')
    Enforces RBAC at the application layer. Query-level scoping (faculty_id/
    department_id) must additionally be applied inside the route — this
    decorator only checks role membership, not data scope.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = get_current_user()
            if user is None or not user.is_active:
                return jsonify({"error": "Authentication required."}), 401
            if user.role not in roles:
                return jsonify({"error": "You do not have permission to access this resource."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
