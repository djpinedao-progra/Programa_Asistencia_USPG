from app.controllers import main
from app.controllers.decorators import roles_required
from app.controllers._support import *
from app.controllers._support import _admin_student_summaries, _admin_session_summaries
from app.views.reports.pdf_builder import (
    build_admin_report_pdf,
    build_session_report_pdf,
)


@main.get("/admin/reportes")
@roles_required("admin")
def admin_reports():
    course_id = request.args.get("curso", type=int)
    courses = CourseRepository().list_all()
    if course_id and not any(course.id == course_id for course in courses):
        abort(404)
    summaries = _admin_student_summaries(course_id=course_id)
    return render_template(
        "admin/admin_reports.html", courses=courses, summaries=summaries,
        selected_course=course_id,
    )


@main.get("/admin/reportes.pdf")
@roles_required("admin")
def admin_reports_pdf():
    course_id = request.args.get("curso", type=int)
    courses = CourseRepository().list_all()
    course = next((item for item in courses if item.id == course_id), None)
    if course_id and not course:
        abort(404)
    summaries = _admin_student_summaries(course_id=course_id)
    title = "Reporte de asistencia" if not course else f"Reporte {course.name}"
    subtitle = "Todos los cursos" if not course else f"Curso {course.code} · {course.schedule or 'Horario pendiente'}"
    output = io.BytesIO(
        build_admin_report_pdf(
            [
                {
                    **row,
                    "student_name": row["student"].name,
                    "student_carnet": row["student"].carnet,
                }
                for row in summaries
            ],
            title,
            subtitle,
        )
    )
    filename = f"reporte-asistencia-{course.code if course else 'general'}.pdf"
    return send_file(output, mimetype="application/pdf", as_attachment=True, download_name=filename)


@main.get("/admin/sesiones/<int:session_id>/reporte.pdf")
@roles_required("admin")
def admin_session_report_pdf(session_id):
    attendance_session = db.session.get(AttendanceSession, session_id)
    if not attendance_session:
        abort(404)
    records = {
        record.student_id: record
        for record in db.session.scalars(
            select(Attendance).where(Attendance.session_id == session_id)
        ).all()
    }
    students = [enrollment.student for enrollment in attendance_session.course.enrollments]
    if not students:
        students = list(
            {
                record.student_id: record.student
                for record in db.session.scalars(
                    select(Attendance).where(Attendance.session_id == session_id)
                ).all()
            }.values()
        )
    rows = []
    for student in sorted(students, key=lambda item: item.name.casefold()):
        record = records.get(student.id)
        recorded_at = record.recorded_at if record else None
        local_recorded_at = (
            local_datetime(recorded_at, current_app.config["APP_TIMEZONE"])
            if recorded_at
            else None
        )
        rows.append(
            {
                "student_name": student.name,
                "carnet": student.carnet,
                "status": record.status.capitalize() if record else "Pendiente",
                "date": local_recorded_at.strftime("%d/%m/%Y") if local_recorded_at else "—",
                "time": local_recorded_at.strftime("%H:%M") if local_recorded_at else "—",
                "source": {"qr": "Código QR", "manual": "Docente", "cierre": "Cierre"}.get(
                    record.source if record else "", "—"
                ),
            }
        )
    course = attendance_session.course
    subtitle = (
        f"{course.code} · Docente: {course.teacher.name} · "
        f"Horario: {course.schedule or '—'} · "
        f"Sesión: {local_datetime(attendance_session.created_at, current_app.config['APP_TIMEZONE']).strftime('%d/%m/%Y %H:%M')}"
    )
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
