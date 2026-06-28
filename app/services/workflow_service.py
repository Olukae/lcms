"""
Curriculum workflow state machine.

    draft -> submitted -> dept_review -> faculty_review -> qa_review -> senate_review -> approved
                              |               |                |
                              +---------------+----------------+--> returned -> (lecturer revises, resubmits -> dept_review)

Implemented as an explicit state machine rather than scattered if/else checks
in route handlers, per the spec (this is flagged as the most failure-prone
part of the system).
"""
from datetime import datetime
from app.extensions import db
from app.models.user import ROLE_LECTURER, ROLE_HOD, ROLE_DEAN, ROLE_QA, ROLE_ADMIN
from app.models.curriculum import (
    Curriculum,
    STATUS_DRAFT, STATUS_SUBMITTED, STATUS_DEPT_REVIEW, STATUS_FACULTY_REVIEW,
    STATUS_QA_REVIEW, STATUS_SENATE_REVIEW, STATUS_APPROVED, STATUS_RETURNED,
)
from app.models.workflow import ApprovalAction, DECISION_APPROVED, DECISION_RETURNED, DECISION_REFERRED
from app.services import version_control_service, audit_service, notification_service


class WorkflowError(Exception):
    """Raised for any invalid workflow transition: wrong role, wrong scope,
    or wrong pre-state. Routes should catch this and surface a 403/409."""
    pass


# Maps the *current* status to the role permitted to act on it, and what the
# "approved" outcome's next status is. This is the single source of truth for
# stage sequencing — nothing else in the app should hardcode this chain.
STAGE_RULES = {
    STATUS_DEPT_REVIEW: {
        "role_required": ROLE_HOD,
        "stage_name": "Departmental Review",
        "next_status": STATUS_FACULTY_REVIEW,
        "scope": "department",
    },
    STATUS_FACULTY_REVIEW: {
        "role_required": ROLE_DEAN,
        "stage_name": "Faculty Board",
        "next_status": STATUS_QA_REVIEW,
        "scope": "faculty",
    },
    STATUS_QA_REVIEW: {
        "role_required": ROLE_QA,
        "stage_name": "Quality Assurance",
        "next_status": STATUS_SENATE_REVIEW,
        "scope": None,  # QA reviews institution-wide, not department/faculty scoped
    },
    STATUS_SENATE_REVIEW: {
        # Resolved ambiguity (see build prompt header note): System Administrator
        # doubles as the Senate/Registry liaison and records the offline Senate
        # sitting's outcome as the final ratification step. This is the only
        # rule that would need to change if Senate becomes its own role.
        "role_required": ROLE_ADMIN,
        "stage_name": "Senate",
        "next_status": STATUS_APPROVED,
        "scope": None,
    },
}


def submit_curriculum(curriculum, user):
    """Only the originating lecturer, only from draft. Sets status to
    dept_review, creates a CurriculumVersion snapshot, notifies the HOD."""
    if user.role != ROLE_LECTURER or curriculum.originating_user_id != user.id:
        raise WorkflowError("Only the originating lecturer may submit this proposal.")
    if curriculum.status not in (STATUS_DRAFT, STATUS_RETURNED):
        raise WorkflowError(
            f"Cannot submit from current status '{curriculum.status}'."
        )

    curriculum.status = STATUS_DEPT_REVIEW
    curriculum.submitted_at = datetime.utcnow()
    curriculum.last_return_comment = None
    db.session.commit()

    version_control_service.snapshot(curriculum, user)

    audit_service.log(
        user, "submit_curriculum", "Curriculum", curriculum.id,
        f"Lecturer submitted curriculum #{curriculum.id} for departmental review."
    )

    hod = _find_recipient(role=ROLE_HOD, department_id=curriculum.department_id)
    if hod:
        notification_service.notify(
            hod,
            f"New curriculum proposal submitted for {curriculum.course.course_code if curriculum.course else 'review'} "
            f"— awaiting departmental review.",
            curriculum=curriculum,
        )

    return curriculum


def record_decision(curriculum, actor, decision, comments=None):
    """Validates the actor's role matches role_required for the current
    stage and that the actor's department_id/faculty_id scopes match the
    curriculum's. On 'approved', advances status to the next stage (or to
    'approved' if this was Senate) and increments current_version_no. On
    'returned', sets status='returned', attaches the comment, and notifies
    the originating lecturer. Every call writes an ApprovalAction row and
    an AuditLog entry.

    Rejects any decision call where curriculum.status doesn't match the
    expected pre-state, preventing race conditions from concurrent reviews.
    """
    current_status = curriculum.status
    rule = STAGE_RULES.get(current_status)
    if rule is None:
        raise WorkflowError(
            f"Curriculum #{curriculum.id} is not in a reviewable state (status='{current_status}')."
        )

    if actor.role != rule["role_required"]:
        raise WorkflowError(
            f"Role '{actor.role}' is not permitted to act at the {rule['stage_name']} stage."
        )

    if rule["scope"] == "department":
        if actor.department_id is None or actor.department_id != curriculum.department_id:
            raise WorkflowError("Actor's department does not match this curriculum's department.")
    elif rule["scope"] == "faculty":
        if actor.faculty_id is None or actor.faculty_id != curriculum.faculty_id:
            raise WorkflowError("Actor's faculty does not match this curriculum's faculty.")

    if decision not in (DECISION_APPROVED, DECISION_RETURNED, DECISION_REFERRED):
        raise WorkflowError(f"Unknown decision type '{decision}'.")

    # Re-check the pre-state right before mutating, guarding against a
    # concurrent decision having already moved this curriculum elsewhere.
    fresh = Curriculum.query.get(curriculum.id)
    if fresh.status != current_status:
        raise WorkflowError(
            "This proposal's status has changed since you loaded it — "
            "someone else may have already actioned it. Please refresh."
        )

    action = ApprovalAction(
        curriculum_id=curriculum.id,
        actor_user_id=actor.id,
        decision=decision,
        comments=comments,
    )
    db.session.add(action)
    db.session.flush()  # get action.id without committing yet

    if decision == DECISION_APPROVED:
        curriculum.status = rule["next_status"]
        db.session.commit()
        version_control_service.snapshot(curriculum, actor, approval_action=action)

        audit_service.log(
            actor, "approve_curriculum", "Curriculum", curriculum.id,
            f"{rule['stage_name']} approved curriculum #{curriculum.id}; advanced to '{curriculum.status}'."
        )
        _notify_next_stage(curriculum)

    else:  # returned or referred — both send the proposal back to the lecturer
        curriculum.status = STATUS_RETURNED
        curriculum.last_return_comment = comments
        db.session.commit()

        audit_service.log(
            actor, f"{decision}_curriculum", "Curriculum", curriculum.id,
            f"{rule['stage_name']} {decision} curriculum #{curriculum.id}."
            + (f" Comment: {comments}" if comments else "")
        )

        if curriculum.originating_user:
            notification_service.notify(
                curriculum.originating_user,
                f"Your proposal for {curriculum.course.course_code if curriculum.course else 'a course'} "
                f"was returned at the {rule['stage_name']} stage. Please review the comments and resubmit.",
                curriculum=curriculum,
            )

    return action


def _notify_next_stage(curriculum):
    status = curriculum.status
    if status == STATUS_FACULTY_REVIEW:
        recipient = _find_recipient(role=ROLE_DEAN, faculty_id=curriculum.faculty_id)
        stage_label = "Faculty Board"
    elif status == STATUS_QA_REVIEW:
        recipient = _find_recipient(role=ROLE_QA)
        stage_label = "Quality Assurance"
    elif status == STATUS_SENATE_REVIEW:
        recipient = _find_recipient(role=ROLE_ADMIN)
        stage_label = "Senate"
    elif status == STATUS_APPROVED:
        if curriculum.originating_user:
            notification_service.notify(
                curriculum.originating_user,
                f"Your proposal for {curriculum.course.course_code if curriculum.course else 'a course'} "
                f"has been approved and ratified by Senate.",
                curriculum=curriculum,
            )
        return
    else:
        return

    if recipient:
        notification_service.notify(
            recipient,
            f"A curriculum proposal has been forwarded to {stage_label} for review.",
            curriculum=curriculum,
        )


def _find_recipient(role, department_id=None, faculty_id=None):
    from app.models.user import User
    query = User.query.filter_by(role=role, is_active=True)
    if department_id is not None:
        query = query.filter_by(department_id=department_id)
    if faculty_id is not None:
        query = query.filter_by(faculty_id=faculty_id)
    return query.first()
