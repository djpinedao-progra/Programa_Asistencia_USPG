from app.controllers import main
from app.controllers.decorators import roles_required
from app.controllers._support import *
from app.views.reports.csv_builder import build_attendance_csv
from app.views.reports.pdf_builder import build_course_attendance_pdf


@main.get("/api/cursos/<int:course_id>/asistencias.csv")
@roles_required("admin", "docente")
def export_attendance(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        abort(404)
    if current_user.role == "docente" and course.teacher_id != current_user.id:
        abort(403)
    rows = AttendanceRepository().list_for_course(course_id)
    csv_rows = [
        (
            row.student.name,
            row.student.carnet or "",
            row.student.email,
            row.session.course.name,
            row.session.course.code,
            row.session.course.teacher.name,
            local_datetime(
                row.recorded_at, current_app.config["APP_TIMEZONE"]
            ).isoformat(),
        )
        for row in rows
    ]
    from flask import Response

    return Response(
        build_attendance_csv(csv_rows),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="asistencias-{course.code}.csv"'},
    )


@main.get("/api/cursos/<int:course_id>/asistencias.pdf")
@roles_required("admin", "docente")
def export_attendance_pdf(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        abort(404)
    if current_user.role == "docente" and course.teacher_id != current_user.id:
        abort(403)

    rows = AttendanceRepository().list_for_course(course_id)
    pdf_rows = [
        (
            row.student.carnet or "-",
            row.student.name,
            row.student.email,
            row.session.course.code,
            row.session.course.teacher.name,
            local_datetime(
                row.recorded_at, current_app.config["APP_TIMEZONE"]
            ).strftime("%d/%m/%Y %H:%M"),
        )
        for row in rows
    ]
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
