from app.extensions import db
from app.models.curriculum import CurriculumVersion

FIELD_LABELS = {
    "course_code": "course code",
    "course_title": "course title",
    "credit_units": "credit units",
    "course_description": "course description",
    "learning_outcomes": "learning outcomes",
    "prerequisites": "prerequisites",
    "assessment_breakdown": "assessment breakdown",
    "reading_list": "reading list",
}

# Fields whose full text is too long to usefully diff inline — we just say "updated".
LONG_TEXT_FIELDS = {"course_description", "learning_outcomes", "prerequisites", "reading_list"}


def _describe_change(field, old_value, new_value):
    label = FIELD_LABELS.get(field, field)
    if field in LONG_TEXT_FIELDS:
        return f"{label} updated"
    if field == "assessment_breakdown":
        return f"{label} changed from {old_value} to {new_value}"
    return f"{label} changed from {old_value!r} to {new_value!r}"


def build_change_summary(previous_snapshot, new_snapshot):
    """Builds a plain-English diff string, e.g.
    'credit_units changed from 3 to 4; learning_outcomes updated'.
    Returns 'Initial version' if there is no previous snapshot.
    """
    if previous_snapshot is None:
        return "Initial version"

    changes = []
    all_fields = set(previous_snapshot.keys()) | set(new_snapshot.keys())
    for field in FIELD_LABELS.keys():
        if field not in all_fields:
            continue
        old_value = previous_snapshot.get(field)
        new_value = new_snapshot.get(field)
        if old_value != new_value:
            changes.append(_describe_change(field, old_value, new_value))

    if not changes:
        return "No field-level changes (workflow status updated)"
    return "; ".join(changes)


def snapshot(curriculum, user, approval_action=None):
    """Writes the full current field set to CurriculumVersion.snapshot_data
    along with a generated change_summary diffed against the previous version.
    This is what lets an authorized user retrieve a complete change history
    per record (TC-09).
    """
    new_data = curriculum.field_snapshot()

    previous = (
        CurriculumVersion.query
        .filter_by(curriculum_id=curriculum.id)
        .order_by(CurriculumVersion.version_no.desc())
        .first()
    )
    previous_data = previous.snapshot_data if previous else None

    next_version_no = (previous.version_no + 1) if previous else 1
    summary = build_change_summary(previous_data, new_data)

    version = CurriculumVersion(
        curriculum_id=curriculum.id,
        version_no=next_version_no,
        snapshot_data=new_data,
        changed_by_user_id=user.id,
        approval_action_id=approval_action.id if approval_action else None,
        change_summary=summary,
    )
    db.session.add(version)
    curriculum.current_version_no = next_version_no
    db.session.commit()
    return version
