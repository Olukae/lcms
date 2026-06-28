from datetime import datetime
from sqlalchemy import func
from app.extensions import db
from app.models.curriculum import Curriculum, STATUS_APPROVED, STATUS_RETURNED
from app.models.workflow import ApprovalAction, DECISION_APPROVED
from app.models.academic import Faculty, Department, Programme, Course


def pending_items_by_stage():
    """Count of curricula currently sitting at each in-progress status."""
    rows = (
        db.session.query(Curriculum.status, func.count(Curriculum.id))
        .filter(Curriculum.status.notin_([STATUS_APPROVED]))
        .group_by(Curriculum.status)
        .all()
    )
    return {status: count for status, count in rows}


def approval_cycle_time_by_stage():
    """Average time (in hours) between consecutive approval actions on the
    same curriculum, grouped by the stage that was just completed. This
    approximates "time spent at each stage" using the ApprovalAction trail.
    """
    results = {}
    curricula_ids = [c.id for c in Curriculum.query.with_entities(Curriculum.id).all()]
    for cid in curricula_ids:
        actions = (
            ApprovalAction.query.filter_by(curriculum_id=cid)
            .order_by(ApprovalAction.created_at)
            .all()
        )
        prev_time = None
        for action in actions:
            if prev_time is not None:
                stage_name = action.workflow_stage.name if action.workflow_stage else action.decision
                hours = (action.created_at - prev_time).total_seconds() / 3600.0
                results.setdefault(stage_name, []).append(hours)
            prev_time = action.created_at

    return {
        stage: round(sum(durations) / len(durations), 2)
        for stage, durations in results.items()
        if durations
    }


def curriculum_activity_by_faculty(start_date=None, end_date=None):
    """Count of curricula created/updated per faculty within an optional date range."""
    query = (
        db.session.query(Faculty.name, func.count(Curriculum.id))
        .join(Department, Department.faculty_id == Faculty.id)
        .join(Programme, Programme.department_id == Department.id)
        .join(Course, Course.programme_id == Programme.id)
        .join(Curriculum, Curriculum.course_id == Course.id)
    )
    if start_date:
        query = query.filter(Curriculum.created_at >= start_date)
    if end_date:
        query = query.filter(Curriculum.created_at <= end_date)
    rows = query.group_by(Faculty.name).all()
    return {name: count for name, count in rows}


def full_history_for_course(course_id):
    """All curriculum records (and their versions) for a given course."""
    curricula = Curriculum.query.filter_by(course_id=course_id).order_by(Curriculum.created_at).all()
    history = []
    for c in curricula:
        history.append({
            "curriculum_id": c.id,
            "status": c.status,
            "current_version_no": c.current_version_no,
            "versions": [
                {
                    "version_no": v.version_no,
                    "change_summary": v.change_summary,
                    "changed_by": v.changed_by.full_name if v.changed_by else None,
                    "created_at": v.created_at.isoformat(),
                }
                for v in c.versions
            ],
        })
    return history


def report_for_date_range(start_date, end_date):
    """Aggregate report used for the downloadable accreditation report (TC-11)."""
    query = Curriculum.query
    if start_date:
        query = query.filter(Curriculum.created_at >= start_date)
    if end_date:
        query = query.filter(Curriculum.created_at <= end_date)
    curricula = query.order_by(Curriculum.created_at).all()

    approved = [c for c in curricula if c.status == STATUS_APPROVED]
    returned = [c for c in curricula if c.status == STATUS_RETURNED]

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "total_curricula": len(curricula),
        "approved_count": len(approved),
        "returned_count": len(returned),
        "pending_by_stage": pending_items_by_stage(),
        "curricula": [
            {
                "id": c.id,
                "course_code": c.course.course_code if c.course else None,
                "course_title": c.course.course_title if c.course else None,
                "status": c.status_label,
                "current_version_no": c.current_version_no,
                "created_at": c.created_at.isoformat(),
            }
            for c in curricula
        ],
    }
