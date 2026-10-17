import io

from flask import abort, current_app, render_template, request, send_file

from app.controllers import main
from app.controllers.decorators import roles_required
from app.services import AttendanceReportService, AttendanceService, CourseService
from app.services.metrics_service import (
    admin_report_pdf_data,
    admin_student_summaries,
)
from app.views.reports.pdf_builder import (
    build_admin_report_pdf,
    build_session_report_pdf,
)


@main.get("/admin/reportes")
@roles_required("admin")
def admin_reports():
    course_id = request.args.get("curso", type=int)
    courses = CourseService().list_all()
    if course_id and not any(course.id == course_id for course in courses):
        abort(404)
    summaries = admin_student_summaries(
        course_id=course_id,
        timezone_name=current_app.config["APP_TIMEZONE"],
    )
    return render_template(
        "admin/admin_reports.html", courses=courses, summaries=summaries,
        selected_course=course_id,
    )


@main.get("/admin/reportes.pdf")
@roles_required("admin")
def admin_reports_pdf():
    course_id = request.args.get("curso", type=int)
    course = CourseService().get_by_id(course_id) if course_id else None
    if course_id and not course:
        abort(404)
    summaries = admin_student_summaries(
        course_id=course_id,
        timezone_name=current_app.config["APP_TIMEZONE"],
    )
    report = admin_report_pdf_data(course, summaries)
    output = io.BytesIO(
        build_admin_report_pdf(
            report["rows"], report["title"], report["subtitle"]
        )
    )
    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=report["filename"],
    )


@main.get("/admin/sesiones/<int:session_id>/reporte.pdf")
@roles_required("admin")
def admin_session_report_pdf(session_id):
    attendance_session, rows, subtitle = AttendanceReportService().session_report_data(
        session_id, current_app.config["APP_TIMEZONE"]
    )
    if not attendance_session:
        abort(404)
    course = attendance_session.course
    output = io.BytesIO(
        build_session_report_pdf(
            f"Reporte de sesión · {course.name}", subtitle, rows
        )
    )
    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"sesion-{course.code}-{attendance_session.id}.pdf",
    )
