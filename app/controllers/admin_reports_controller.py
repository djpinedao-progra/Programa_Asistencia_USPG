from app.controllers import main
from app.controllers.decorators import roles_required
from app.controllers._support import *
from app.controllers._support import _admin_student_summaries, _admin_session_summaries


@main.get("/admin/reportes")
@roles_required("admin")
def admin_reports():
    course_id = request.args.get("curso", type=int)
    courses = CourseRepository().list_all()
    if course_id and not any(course.id == course_id for course in courses):
        abort(404)
    summaries = _admin_student_summaries(course_id=course_id)
    return render_template(
        "admin_reports.html", courses=courses, summaries=summaries,
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
    output = _admin_report_pdf(summaries, title, subtitle)
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
    data = [["Estudiante", "Carnet", "Estado", "Fecha", "Hora", "Origen"]]
    for student in sorted(students, key=lambda item: item.name.casefold()):
        record = records.get(student.id)
        recorded_at = record.recorded_at if record else None
        data.append(
            [
                Paragraph(escape(student.name), getSampleStyleSheet()["BodyText"]),
                student.carnet or "—",
                record.status.capitalize() if record else "Pendiente",
                local_datetime(recorded_at, current_app.config["APP_TIMEZONE"]).strftime(
                    "%d/%m/%Y"
                ) if recorded_at else "—",
                local_datetime(recorded_at, current_app.config["APP_TIMEZONE"]).strftime(
                    "%H:%M"
                ) if recorded_at else "—",
                {"qr": "Código QR", "manual": "Docente", "cierre": "Cierre"}.get(
                    record.source if record else "", "—"
                ),
            ]
        )
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=landscape(letter), title="Reporte de sesión"
    )
    styles = getSampleStyleSheet()
    course = attendance_session.course
    story = [
        Paragraph(escape(f"Reporte de sesión · {course.name}"), styles["Title"]),
        Paragraph(
            escape(
                f"{course.code} · Docente: {course.teacher.name} · "
                f"Horario: {course.schedule or '—'} · "
                f"Sesión: {local_datetime(attendance_session.created_at, current_app.config['APP_TIMEZONE']).strftime('%d/%m/%Y %H:%M')}"
            ),
            styles["BodyText"],
        ),
        Spacer(1, 8 * mm),
    ]
    table = Table(data, repeatRows=1, colWidths=[65 * mm, 30 * mm, 35 * mm, 35 * mm, 30 * mm, 45 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#292324")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8cfd0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f2f3")]),
            ]
        )
    )
    story.append(table)
    document.build(story)
    output.seek(0)
    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"sesion-{course.code}-{attendance_session.id}.pdf",
    )


def _admin_report_pdf(summaries, title, subtitle):
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=title,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(escape(title), styles["Title"]),
        Paragraph(escape(subtitle), styles["BodyText"]),
        Spacer(1, 9 * mm),
    ]
    chart_rows = summaries[:14]
    if chart_rows:
        chart_height = max(70, len(chart_rows) * 18 + 10)
        chart = Drawing(520, chart_height)
        for index, row in enumerate(chart_rows):
            y = chart_height - 20 - index * 18
            pct = row["percentage"]
            color = colors.HexColor(
                "#b5122b" if row["risk"] == "alto"
                else "#c58a24" if row["risk"] == "medio"
                else "#47745d"
            )
            chart.add(
                String(0, y + 2, row["student"].name[:25], fontSize=8)
            )
            chart.add(
                Rect(150, y, max(1, pct * 2.8), 10, fillColor=color, strokeColor=None)
            )
            chart.add(String(455, y + 2, f"{pct}%", fontSize=8))
        story.extend([chart, Spacer(1, 5 * mm)])
    data = [["Estudiante", "Carnet", "Cursos", "Sesiones", "Presentes", "Faltas", "Justificadas", "%", "Riesgo"]]
    for row in summaries:
        data.append(
            [
                Paragraph(escape(row["student"].name), styles["BodyText"]),
                row["student"].carnet or "—",
                Paragraph(escape(row["course_names"] or "—"), styles["BodyText"]),
                str(row["total_sessions"]),
                str(row["present"]),
                str(row["absent"]),
                str(row["justified"]),
                f"{row['percentage']}%",
                row["risk"].capitalize(),
            ]
        )
    table = Table(data, repeatRows=1, colWidths=[37 * mm, 22 * mm, 52 * mm, 17 * mm, 17 * mm, 15 * mm, 21 * mm, 12 * mm, 19 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#292324")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("LEADING", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8cfd0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f2f3")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    document.build(story)
    output.seek(0)
    return output
