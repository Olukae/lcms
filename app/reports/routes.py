from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from app.auth.decorators import role_required, get_current_user
from app.models.user import ROLE_DEAN, ROLE_QA, ROLE_ADMIN
from app.services import report_service, pdf_service

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@bp.route("/aggregate", methods=["GET"])
@role_required(ROLE_DEAN, ROLE_QA, ROLE_ADMIN)
def aggregate_report():
    """TC-11: report produced for a date range. Dean's view is faculty-scoped
    elsewhere in the UI (the underlying query here returns institution-wide
    data; the dashboard template filters faculty-scoped views for Deans)."""
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))

    data = report_service.report_for_date_range(start_date, end_date)
    return jsonify({"report": data}), 200


@bp.route("/aggregate/export.pdf", methods=["GET"])
@role_required(ROLE_DEAN, ROLE_QA, ROLE_ADMIN)
def export_aggregate_pdf():
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))

    data = report_service.report_for_date_range(start_date, end_date)
    try:
        buffer = pdf_service.report_to_pdf(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 500

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="lcms_accreditation_report.pdf",
    )


@bp.route("/pending-by-stage", methods=["GET"])
@role_required(ROLE_DEAN, ROLE_QA, ROLE_ADMIN)
def pending_by_stage():
    return jsonify({"pending_by_stage": report_service.pending_items_by_stage()}), 200


@bp.route("/cycle-time", methods=["GET"])
@role_required(ROLE_QA, ROLE_ADMIN)
def cycle_time():
    return jsonify({"cycle_time_hours": report_service.approval_cycle_time_by_stage()}), 200
