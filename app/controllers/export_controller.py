from app.controllers import main
from app.controllers.decorators import roles_required
from app.controllers._support import *


@main.get("/api/cursos/<int:course_id>/asistencias.csv")
@roles_required("admin", "docente")
def export_attendance(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        abort(404)
    if current_user.role == "docente" and course.teacher_id != current_user.id:
        abort(403)
    rows = AttendanceRepository().list_for_course(course_id)
    lines = ["alumno,carnet,correo,curso,codigo,docente,fecha_hora"]
    for row in rows:
        values = (
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
        lines.append(",".join('"' + value.replace('"', '""') + '"' for value in values))
    from flask import Response

    return Response(
        "\ufeff" + "\n".join(lines),
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
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Asistencias {course.code}",
    )
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(
        "AttendanceCell", parent=styles["BodyText"], fontName="Helvetica", fontSize=7
    )
    story = [
        Paragraph(f"Registros de asistencia · {escape(course.name)}", styles["Title"]),
        Paragraph(
            f"Curso: {escape(course.code)} · Docente: {escape(course.teacher.name)}",
            styles["BodyText"],
        ),
        Spacer(1, 6 * mm),
    ]
    data = [["Carnet", "Estudiante", "Correo", "Curso", "Docente", "Fecha y hora"]]
    for row in rows:
        values = (
            row.student.carnet or "-",
            row.student.name,
            row.student.email,
            row.session.course.code,
            row.session.course.teacher.name,
            local_datetime(
                row.recorded_at, current_app.config["APP_TIMEZONE"]
            ).strftime("%d/%m/%Y %H:%M"),
        )
        data.append([Paragraph(escape(value), cell_style) for value in values])
    if not rows:
        story.append(Paragraph("Todavía no hay asistencias registradas.", styles["BodyText"]))
    else:
        table = Table(data, repeatRows=1, colWidths=[23 * mm, 39 * mm, 52 * mm, 24 * mm, 39 * mm, 34 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#126b60")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f5f1")]),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#dfe7e3")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
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
        download_name=f"asistencias-{course.code}.pdf",
    )
