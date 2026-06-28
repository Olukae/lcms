from io import BytesIO
from flask import render_template
from xhtml2pdf import pisa


def render_pdf(template_name, **context):
    """Renders a Jinja template to PDF bytes via xhtml2pdf. Returns a
    BytesIO buffer positioned at 0, ready to send as a file response.
    Raises ValueError if rendering fails so the route can surface a 500
    with a useful message instead of silently returning a blank file.
    """
    html = render_template(template_name, **context)
    buffer = BytesIO()
    result = pisa.CreatePDF(src=html, dest=buffer)
    if result.err:
        raise ValueError(f"PDF generation failed with {result.err} error(s).")
    buffer.seek(0)
    return buffer


def curriculum_to_pdf(curriculum):
    return render_pdf("reports/curriculum_pdf.html", curriculum=curriculum)


def report_to_pdf(report_data):
    return render_pdf("reports/aggregate_report_pdf.html", report=report_data)
