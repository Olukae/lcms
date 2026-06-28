from flask import Blueprint, render_template, request, jsonify
from app.extensions import db
from app.auth.decorators import role_required, get_current_user
from app.models.user import User, ROLE_ADMIN, ALL_ROLES, ROLE_LABELS
from app.models.academic import Faculty, Department, Programme, Course
from app.models.curriculum import Curriculum, STATUS_SENATE_REVIEW
from app.models.audit import AuditLog
from app.services import notification_service, workflow_service, audit_service
from app.services.workflow_service import WorkflowError

bp = Blueprint("dashboard_admin", __name__, url_prefix="/dashboard/admin")


@bp.route("", methods=["GET"])
@role_required(ROLE_ADMIN)
def index():
    user = get_current_user()
    senate_pending = Curriculum.query.filter_by(status=STATUS_SENATE_REVIEW).order_by(
        Curriculum.updated_at
    ).all()
    user_count = User.query.count()
    faculty_count = Faculty.query.count()

    return render_template(
        "dashboards/admin.html",
        user=user,
        senate_pending=senate_pending,
        user_count=user_count,
        faculty_count=faculty_count,
        unread_count=notification_service.unread_count(user),
    )


@bp.route("/senate/<int:curriculum_id>/ratify", methods=["POST"])
@role_required(ROLE_ADMIN)
def ratify_senate(curriculum_id):
    """Records the outcome of the offline Senate sitting. Per the resolved
    ambiguity in the build prompt, the System Administrator role doubles as
    the Senate/Registry liaison for this final ratification step."""
    user = get_current_user()
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    data = request.get_json(silent=True) or {}
    decision = data.get("decision", "approved")
    comments = data.get("comments")

    try:
        workflow_service.record_decision(curriculum, user, decision, comments)
    except WorkflowError as e:
        return jsonify({"error": str(e)}), 409

    return jsonify({"message": "Senate decision recorded.", "status": curriculum.status}), 200


# ---- User management ----

@bp.route("/users", methods=["GET"])
@role_required(ROLE_ADMIN)
def list_users():
    users = User.query.order_by(User.full_name).all()
    return jsonify({"users": [u.to_dict() for u in users]}), 200


@bp.route("/users", methods=["POST"])
@role_required(ROLE_ADMIN)
def create_user():
    admin = get_current_user()
    data = request.get_json(silent=True) or {}

    required = ["full_name", "email", "password", "role"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    if data["role"] not in ALL_ROLES:
        return jsonify({"error": f"Invalid role. Must be one of {ALL_ROLES}."}), 400

    if data["role"] in ("lecturer", "hod") and not data.get("department_id"):
        return jsonify({"error": "department_id is required for lecturer/hod roles."}), 400

    if User.query.filter(db.func.lower(User.email) == data["email"].strip().lower()).first():
        return jsonify({"error": "A user with this email already exists."}), 409

    user = User(
        full_name=data["full_name"],
        email=data["email"].strip().lower(),
        role=data["role"],
        faculty_id=data.get("faculty_id"),
        department_id=data.get("department_id"),
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    audit_service.log(
        admin, "create_user", "User", user.id,
        f"Admin created user {user.email} with role {user.role}."
    )

    return jsonify({"user": user.to_dict()}), 201


@bp.route("/users/<int:user_id>", methods=["PUT"])
@role_required(ROLE_ADMIN)
def update_user(user_id):
    admin = get_current_user()
    target = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    if "full_name" in data:
        target.full_name = data["full_name"]
    if "role" in data:
        if data["role"] not in ALL_ROLES:
            return jsonify({"error": f"Invalid role. Must be one of {ALL_ROLES}."}), 400
        target.role = data["role"]
    if "faculty_id" in data:
        target.faculty_id = data["faculty_id"]
    if "department_id" in data:
        target.department_id = data["department_id"]
    if "is_active" in data:
        target.is_active = bool(data["is_active"])

    db.session.commit()
    audit_service.log(
        admin, "update_user", "User", target.id, f"Admin updated user {target.email}."
    )
    return jsonify({"user": target.to_dict()}), 200


@bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@role_required(ROLE_ADMIN)
def deactivate_user(user_id):
    admin = get_current_user()
    target = User.query.get_or_404(user_id)
    target.is_active = False
    db.session.commit()
    audit_service.log(
        admin, "deactivate_user", "User", target.id, f"Admin deactivated user {target.email}."
    )
    return jsonify({"user": target.to_dict()}), 200


# ---- Faculty / Department / Programme / Course CRUD ----

@bp.route("/faculties", methods=["GET", "POST"])
@role_required(ROLE_ADMIN)
def faculties():
    admin = get_current_user()
    if request.method == "GET":
        items = Faculty.query.order_by(Faculty.name).all()
        return jsonify({"faculties": [
            {"id": f.id, "name": f.name, "code": f.code} for f in items
        ]}), 200

    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("code"):
        return jsonify({"error": "name and code are required."}), 400
    faculty = Faculty(name=data["name"], code=data["code"])
    db.session.add(faculty)
    db.session.commit()
    audit_service.log(admin, "create_faculty", "Faculty", faculty.id, f"Created faculty {faculty.code}.")
    return jsonify({"faculty": {"id": faculty.id, "name": faculty.name, "code": faculty.code}}), 201


@bp.route("/departments", methods=["GET", "POST"])
@role_required(ROLE_ADMIN)
def departments():
    admin = get_current_user()
    if request.method == "GET":
        items = Department.query.order_by(Department.name).all()
        return jsonify({"departments": [
            {"id": d.id, "name": d.name, "code": d.code, "faculty_id": d.faculty_id} for d in items
        ]}), 200

    data = request.get_json(silent=True) or {}
    required = ["faculty_id", "name", "code"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    dept = Department(faculty_id=data["faculty_id"], name=data["name"], code=data["code"])
    db.session.add(dept)
    db.session.commit()
    audit_service.log(admin, "create_department", "Department", dept.id, f"Created department {dept.code}.")
    return jsonify({"department": {"id": dept.id, "name": dept.name, "code": dept.code,
                                    "faculty_id": dept.faculty_id}}), 201


@bp.route("/programmes", methods=["POST"])
@role_required(ROLE_ADMIN)
def programmes():
    admin = get_current_user()
    data = request.get_json(silent=True) or {}
    required = ["department_id", "name", "degree_type"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    prog = Programme(
        department_id=data["department_id"], name=data["name"],
        degree_type=data["degree_type"], nuc_code=data.get("nuc_code"),
    )
    db.session.add(prog)
    db.session.commit()
    audit_service.log(admin, "create_programme", "Programme", prog.id, f"Created programme {prog.name}.")
    return jsonify({"programme": {"id": prog.id, "name": prog.name}}), 201


@bp.route("/courses", methods=["GET"])
@role_required(ROLE_ADMIN)
def courses():
    items = Course.query.order_by(Course.course_code).all()
    return jsonify({"courses": [
        {"id": c.id, "course_code": c.course_code, "course_title": c.course_title,
         "credit_units": c.credit_units, "programme_id": c.programme_id} for c in items
    ]}), 200


# ---- Audit log ----

@bp.route("/audit-log", methods=["GET"])
@role_required(ROLE_ADMIN)
def audit_log():
    """TC-10: all actions shown with timestamps. Supports basic pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)

    query = AuditLog.query.order_by(AuditLog.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "entries": [
            {
                "id": e.id,
                "user": e.user.full_name if e.user else "System",
                "action_type": e.action_type,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "description": e.description,
                "ip_address": e.ip_address,
                "created_at": e.created_at.isoformat(),
            }
            for e in pagination.items
        ],
        "page": pagination.page,
        "total_pages": pagination.pages,
        "total_count": pagination.total,
    }), 200
