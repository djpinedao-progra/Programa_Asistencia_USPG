import io

from flask import Response, abort, current_app, send_file
from flask_login import current_user

from app.controllers import main
from app.controllers.decorators import roles_required
from app.services import AttendanceReportService
from app.views.reports.csv_builder import build_attendance_csv
from app.views.reports.pdf_builder import build_course_attendance_pdf


@main.get("/api/cursos/<int:course_id>/asistencias.csv")
@roles_required("admin", "docente")
def export_attendance(course_id):
    course, csv_rows, _ = AttendanceReportService().course_export_data(
        course_id, current_app.config["APP_TIMEZONE"]
    )
    if not course:
        abort(404)
    if current_user.role == "docente" and course.teacher_id != current_user.id:
        abort(403)
    return Response(
        build_attendance_csv(csv_rows),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="asistencias-{course.code}.csv"'},
    )


@main.get("/api/cursos/<int:course_id>/asistencias.pdf")
@roles_required("admin", "docente")
def export_attendance_pdf(course_id):
    course, _, pdf_rows = AttendanceReportService().course_export_data(
        course_id, current_app.config["APP_TIMEZONE"]
    )
    if not course:
        abort(404)
    if current_user.role == "docente" and course.teacher_id != current_user.id:
        abort(403)

    output = io.BytesIO(
        build_course_attendance_pdf(
            course.name, course.code, course.teacher.name, pdf_rows
        )
    )
    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"asistencias-{course.code}.pdf",
    )
