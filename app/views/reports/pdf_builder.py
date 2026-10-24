"""Generación de documentos PDF a partir de estructuras de datos."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def build_admin_report_pdf(summaries, title, subtitle):
    """Construye el PDF administrativo con resúmenes de asistencia."""
    output = BytesIO()
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
    chart_rows = [row for row in summaries if row["total_sessions"]][:14]
    if chart_rows:
        chart_height = max(70, len(chart_rows) * 18 + 10)
        chart = Drawing(520, chart_height)
        for index, row in enumerate(chart_rows):
            y = chart_height - 20 - index * 18
            percentage = row["percentage"]
            color = colors.HexColor(
                "#b5122b"
                if row["risk"] == "alto"
                else "#c58a24"
                if row["risk"] == "medio"
                else "#47745d"
            )
            chart.add(String(0, y + 2, row["student_name"][:25], fontSize=8))
            chart.add(
                Rect(
                    150,
                    y,
                    max(1, percentage * 2.8),
                    10,
                    fillColor=color,
                    strokeColor=None,
                )
            )
            chart.add(String(455, y + 2, f"{percentage}%", fontSize=8))
        story.extend([chart, Spacer(1, 5 * mm)])
    data = [
        [
            "Estudiante",
            "Carnet",
            "Cursos",
            "Sesiones",
            "Presentes",
            "Faltas",
            "Justificadas",
            "%",
            "Riesgo",
        ]
    ]
    for row in summaries:
        data.append(
            [
                Paragraph(escape(row["student_name"]), styles["BodyText"]),
                row["student_carnet"] or "—",
                Paragraph(escape(row["course_names"] or "—"), styles["BodyText"]),
                str(row["total_sessions"]),
                str(row["present"]),
                str(row["absent"]),
                str(row["justified"]),
                _percentage_label(row),
                row["risk"].capitalize() if row["total_sessions"] else "Sin sesiones",
            ]
        )
    table = Table(
        data,
        repeatRows=1,
        colWidths=[37 * mm, 22 * mm, 52 * mm, 17 * mm, 17 * mm, 15 * mm, 21 * mm, 12 * mm, 19 * mm],
    )
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
    return output.getvalue()


def _percentage_label(row):
    return f"{row['percentage']}%" if row["total_sessions"] else "Sin sesiones"


def build_session_report_pdf(title, subtitle, rows):
    """Construye el PDF de una sesión a partir de sus metadatos y filas."""
    styles = getSampleStyleSheet()
    data = [["Estudiante", "Carnet", "Estado", "Fecha", "Hora", "Origen"]]
    for row in rows:
        data.append(
            [
                Paragraph(escape(row["student_name"]), styles["BodyText"]),
                row["carnet"] or "—",
                row["status"],
                row["date"],
                row["time"],
                row["source"],
            ]
        )
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=landscape(letter), title="Reporte de sesión")
    story = [
        Paragraph(escape(title), styles["Title"]),
        Paragraph(escape(subtitle), styles["BodyText"]),
        Spacer(1, 8 * mm),
    ]
    table = Table(
        data,
        repeatRows=1,
        colWidths=[65 * mm, 30 * mm, 35 * mm, 35 * mm, 30 * mm, 45 * mm],
    )
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
    return output.getvalue()


def build_course_attendance_pdf(course_name, course_code, teacher_name, rows):
    """Construye el PDF de asistencias de un curso a partir de filas preparadas."""
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Asistencias {course_code}",
    )
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(
        "AttendanceCell", parent=styles["BodyText"], fontName="Helvetica", fontSize=7
    )
    story = [
        Paragraph(f"Registros de asistencia · {escape(course_name)}", styles["Title"]),
        Paragraph(
            f"Curso: {escape(course_code)} · Docente: {escape(teacher_name)}",
            styles["BodyText"],
        ),
        Spacer(1, 6 * mm),
    ]
    data = [["Carnet", "Estudiante", "Correo", "Curso", "Docente", "Fecha y hora"]]
    for row in rows:
        data.append([Paragraph(escape(value), cell_style) for value in row])
    if not rows:
        story.append(Paragraph("Todavía no hay asistencias registradas.", styles["BodyText"]))
    else:
        table = Table(
            data,
            repeatRows=1,
            colWidths=[23 * mm, 39 * mm, 52 * mm, 24 * mm, 39 * mm, 34 * mm],
        )
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
    return output.getvalue()


def build_expo_report_pdf(category, categories, counts, attendees):
    """Construye el informe PDF de Expo con conteos y asistentes preparados."""
    styles = getSampleStyleSheet()

    def paragraph(value, style="BodyText"):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), styles[style])

    story = [
        paragraph("Expo San Pablo — Reporte de asistencia", "Title"),
        paragraph("Total general: " + str(sum(counts.values()))),
    ]
    data = [["Categoría", "Asistentes"]] + [
        [label, str(counts.get(key, 0))] for key, label in categories.items()
    ]
    table = Table(data, colWidths=[320, 120])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9eef3")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story += [
        Spacer(1, 12),
        table,
        Spacer(1, 18),
        paragraph("Detalle: " + categories.get(category, "Todos"), "Heading2"),
    ]
    for attendee in attendees:
        story += [
            paragraph(attendee["name"], "Heading3"),
            paragraph(attendee["email"] + " · " + categories[attendee["category"]]),
            paragraph("Registro: " + attendee["recorded_at"] + " (Guatemala)"),
            paragraph("Participación: " + attendee["participation"]),
            paragraph("Opinión: " + (attendee["opinion"] or "Sin opinión")),
            Spacer(1, 10),
        ]
    if not attendees:
        story.append(paragraph("No hay asistentes registrados para esta selección."))

    def footer(canvas, document):
        canvas.setFont("Helvetica", 9)
        canvas.drawString(36, 22, "Expo San Pablo · Página " + str(document.page))

    output = BytesIO()
    SimpleDocTemplate(
        output, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
