from datetime import datetime

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.auth.decorators import login_required, role_required, get_current_user
from app.models.user import ROLE_LECTURER
from app.models.academic import Course, Programme
from app.models.curriculum import Curriculum, CurriculumVersion, STATUS_DRAFT, STATUS_RETURNED
from app.services import workflow_service, audit_service, pdf_service
from app.services.workflow_service import WorkflowError

bp = Blueprint("curriculum", __name__, url_prefix="/api/curriculum")


def _curriculum_to_dict(c, include_versions=False):
    data = {
        "id": c.id,
        "status": c.status,
        "status_label": c.status_label,
        "current_version_no": c.current_version_no,
        "course": {
            "id": c.course.id,
            "course_code": c.course.course_code,
            "course_title": c.course.course_title,
            "credit_units": c.course.credit_units,
            "level": c.course.level,
            "semester": c.course.semester,
        } if c.course else None,
        "course_description": c.course_description,
        "learning_outcomes": c.learning_outcomes,
        "prerequisites": c.prerequisites,
        "assessment_breakdown": c.assessment_breakdown,
        "reading_list": c.reading_list,
        "last_return_comment": c.last_return_comment,
        "originating_user": c.originating_user.full_name if c.originating_user else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "submitted_at": c.submitted_at.isoformat() if c.submitted_at else None,
        "last_autosaved_at": c.last_autosaved_at.isoformat() if c.last_autosaved_at else None,
    }
    if include_versions:
        data["versions"] = [
            {
                "version_no": v.version_no,
                "change_summary": v.change_summary,
                "changed_by": v.changed_by.full_name if v.changed_by else None,
                "created_at": v.created_at.isoformat(),
                "snapshot_data": v.snapshot_data,
            }
            for v in c.versions
        ]
    return data


@bp.route("", methods=["POST"])
@role_required(ROLE_LECTURER)
def create_curriculum():
    """Creates a new draft curriculum (and its underlying Course record if
    one doesn't already exist for this code within the programme)."""
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    required = ["programme_id", "course_code", "course_title", "credit_units"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    programme = Programme.query.get(data["programme_id"])
    if programme is None:
        return jsonify({"error": "Programme not found."}), 404

    course = Course(
        programme_id=programme.id,
        course_code=data["course_code"],
        course_title=data["course_title"],
        credit_units=data["credit_units"],
        level=data.get("level"),
        semester=data.get("semester"),
    )
    db.session.add(course)
    db.session.flush()

    curriculum = Curriculum(
        course_id=course.id,
        originating_user_id=user.id,
        status=STATUS_DRAFT,
        course_description=data.get("course_description"),
        learning_outcomes=data.get("learning_outcomes"),
        prerequisites=data.get("prerequisites"),
        assessment_breakdown=data.get("assessment_breakdown"),
        reading_list=data.get("reading_list"),
    )
    db.session.add(curriculum)
    db.session.commit()

    audit_service.log(
        user, "create_curriculum", "Curriculum", curriculum.id,
        f"Lecturer created draft curriculum for {course.course_code}."
    )

    return jsonify({"curriculum": _curriculum_to_dict(curriculum)}), 201


@bp.route("/<int:curriculum_id>", methods=["GET"])
@login_required
def get_curriculum(curriculum_id):
    user = get_current_user()
    curriculum = Curriculum.query.get_or_404(curriculum_id)

    if not _can_view(user, curriculum):
        return jsonify({"error": "You do not have permission to view this proposal."}), 403

    return jsonify({"curriculum": _curriculum_to_dict(curriculum, include_versions=True)}), 200


def _can_view(user, curriculum):
    if user.role == ROLE_LECTURER:
        return curriculum.originating_user_id == user.id
    if user.role == "hod":
        return user.department_id == curriculum.department_id
    if user.role == "dean":
        return user.faculty_id == curriculum.faculty_id
    if user.role in ("qa_officer", "admin"):
        return True
    return False


@bp.route("/<int:curriculum_id>", methods=["PUT"])
@role_required(ROLE_LECTURER)
def edit_curriculum(curriculum_id):
    """Full edit of a draft (or returned) curriculum's NUC fields. Only the
    originating lecturer, only while in draft/returned status — once it's
    in the review pipeline it must go through workflow actions, not direct
    edits, to preserve the integrity of what reviewers approved."""
    user = get_current_user()
    curriculum = Curriculum.query.get_or_404(curriculum_id)

    if curriculum.originating_user_id != user.id:
        return jsonify({"error": "You may only edit your own proposals."}), 403
    if curriculum.status not in (STATUS_DRAFT, STATUS_RETURNED):
        return jsonify({"error": f"Cannot edit a proposal in status '{curriculum.status}'."}), 409

    data = request.get_json(silent=True) or {}

    for field in ["course_description", "learning_outcomes", "prerequisites",
                  "assessment_breakdown", "reading_list"]:
        if field in data:
            setattr(curriculum, field, data[field])

    course = curriculum.course
    if course:
        for field in ["course_code", "course_title", "credit_units", "level", "semester"]:
            if field in data and data[field] is not None:
                setattr(course, field, data[field])

    if curriculum.status == STATUS_RETURNED:
        curriculum.status = STATUS_DRAFT

    curriculum.draft_data = None
    db.session.commit()

    audit_service.log(
        user, "edit_curriculum", "Curriculum", curriculum.id,
        "Lecturer edited curriculum draft."
    )

    return jsonify({"curriculum": _curriculum_to_dict(curriculum)}), 200


@bp.route("/<int:curriculum_id>/autosave", methods=["PATCH"])
@role_required(ROLE_LECTURER)
def autosave_curriculum(curriculum_id):
    """Writes to draft_data/last_autosaved_at without creating a new
    CurriculumVersion — versions are only created on workflow transitions,
    not on every autosave tick. Fires every ~30s or on blur from the client.
    """
    user = get_current_user()
    curriculum = Curriculum.query.get_or_404(curriculum_id)

    if curriculum.originating_user_id != user.id:
        return jsonify({"error": "You may only autosave your own proposals."}), 403
    if curriculum.status not in (STATUS_DRAFT, STATUS_RETURNED):
        return jsonify({"error": "Autosave is only available while editing a draft."}), 409

    data = request.get_json(silent=True) or {}
    curriculum.draft_data = data.get("draft_data", data)
    curriculum.last_autosaved_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "message": "saved",
        "last_autosaved_at": curriculum.last_autosaved_at.isoformat(),
    }), 200


@bp.route("/<int:curriculum_id>/submit", methods=["POST"])
@role_required(ROLE_LECTURER)
def submit_curriculum(curriculum_id):
    user = get_current_user()
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    try:
        workflow_service.submit_curriculum(curriculum, user)
    except WorkflowError as e:
        return jsonify({"error": str(e)}), 409
    return jsonify({"curriculum": _curriculum_to_dict(curriculum)}), 200


@bp.route("/<int:curriculum_id>/decision", methods=["POST"])
@login_required
def record_decision(curriculum_id):
    """HOD/Dean/QA/Admin approve, return, or refer a proposal at their stage."""
    user = get_current_user()
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    data = request.get_json(silent=True) or {}

    decision = data.get("decision")
    comments = data.get("comments")

    if decision not in ("approved", "returned", "referred"):
        return jsonify({"error": "decision must be 'approved', 'returned', or 'referred'."}), 400
    if decision in ("returned", "referred") and not comments:
        return jsonify({"error": "Comments are required when returning or referring a proposal."}), 400

    try:
        workflow_service.record_decision(curriculum, user, decision, comments)
    except WorkflowError as e:
        return jsonify({"error": str(e)}), 409

    return jsonify({"curriculum": _curriculum_to_dict(curriculum)}), 200


@bp.route("/<int:curriculum_id>/history", methods=["GET"])
@login_required
def curriculum_history(curriculum_id):
    """TC-09: all versions shown with timestamps."""
    user = get_current_user()
    curriculum = Curriculum.query.get_or_404(curriculum_id)

    if not _can_view(user, curriculum):
        return jsonify({"error": "You do not have permission to view this proposal's history."}), 403

    versions = CurriculumVersion.query.filter_by(curriculum_id=curriculum.id).order_by(CurriculumVersion.version_no).all()
    return jsonify({
        "curriculum_id": curriculum.id,
        "versions": [
            {
                "version_no": v.version_no,
                "change_summary": v.change_summary,
                "changed_by": v.changed_by.full_name if v.changed_by else None,
                "created_at": v.created_at.isoformat(),
                "snapshot_data": v.snapshot_data,
            }
            for v in versions
        ],
    }), 200


@bp.route("/<int:curriculum_id>/export.pdf", methods=["GET"])
@login_required
def export_curriculum_pdf(curriculum_id):
    user = get_current_user()
    curriculum = Curriculum.query.get_or_404(curriculum_id)

    if not _can_view(user, curriculum):
        return jsonify({"error": "You do not have permission to export this proposal."}), 403

    try:
        buffer = pdf_service.curriculum_to_pdf(curriculum)
    except ValueError as e:
        return jsonify({"error": str(e)}), 500

    from flask import send_file
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"curriculum_{curriculum.id}_{curriculum.course.course_code if curriculum.course else ''}.pdf",
    )


@bp.route("/programmes", methods=["GET"])
@login_required
def list_programmes():
    """Minimal read used by the proposal-creation form to populate the
    programme dropdown. Intentionally exposes only id/name — full programme
    CRUD lives under /dashboard/admin/programmes (admin-only)."""
    programmes = Programme.query.order_by(Programme.name).all()
    return jsonify({"programmes": [{"id": p.id, "name": p.name} for p in programmes]}), 200


@bp.route("/mine", methods=["GET"])
@role_required(ROLE_LECTURER)
def my_curricula():
    user = get_current_user()
    curricula = Curriculum.query.filter_by(originating_user_id=user.id).order_by(
        Curriculum.updated_at.desc()
    ).all()
    return jsonify({"curricula": [_curriculum_to_dict(c) for c in curricula]}), 200
