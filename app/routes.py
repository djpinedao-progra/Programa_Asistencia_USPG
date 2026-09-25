import base64
import io
import secrets
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urljoin

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from app import db
from app.models import AttendanceSession, Course
from app.repositories import AttendanceRepository, CourseRepository, UserRepository
from app.services import AttendanceService, CourseService, UserService

main = Blueprint("main", __name__)


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


@main.route("/", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = UserRepository().find_by_login_identifier(identifier)
        if user and user.check_password(password):
            login_user(user)
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("main.dashboard"))
        flash("Correo o contraseña incorrectos.", "error")
    return render_template("login.html")


@main.route("/registro", methods=["GET", "POST"])
def student_registration():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        try:
            UserService().register_student(
                request.form.get("name", ""),
                request.form.get("email", ""),
                request.form.get("carnet", ""),
                request.form.get("password", ""),
            )
            flash("Cuenta de estudiante creada. Inicia sesión para continuar.", "success")
            return redirect(url_for("main.login"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template("register.html")


@main.post("/salir")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("main.login"))


@main.get("/panel")
@login_required
def dashboard():
    if current_user.role == "admin":
        return redirect(url_for("main.admin_dashboard"))
    if current_user.role == "docente":
        return redirect(url_for("main.teacher_dashboard"))
    return redirect(url_for("main.student_dashboard"))


@main.route("/admin", methods=["GET", "POST"])
@roles_required("admin")
def admin_dashboard():
    if request.method == "POST":
        try:
            UserService().create_user(
                request.form.get("name", ""),
                request.form.get("email", ""),
                request.form.get("password", ""),
                request.form.get("role", ""),
                request.form.get("carnet", ""),
            )
            flash("Usuario creado correctamente.", "success")
            return redirect(url_for("main.admin_dashboard"))
        except ValueError as error:
            flash(str(error), "error")
    users = UserRepository().list_all()
    courses = CourseRepository().list_all()
    attendances = AttendanceRepository().list_all()
    return render_template(
        "admin.html", users=users, courses=courses, attendances=attendances
    )


@main.post("/admin/usuarios/<int:user_id>/carnet")
@roles_required("admin")
def update_student_carnet(user_id):
    try:
        UserService().assign_student_carnet(
            user_id, request.form.get("carnet", "")
        )
        flash("Carnet actualizado.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("main.admin_dashboard"))


@main.route("/docente", methods=["GET", "POST"])
@roles_required("docente")
def teacher_dashboard():
    if request.method == "POST":
        try:
            CourseService().create_course(
                request.form.get("name", ""),
                request.form.get("code", ""),
                current_user.id,
            )
            flash("Curso creado correctamente.", "success")
            return redirect(url_for("main.teacher_dashboard"))
        except ValueError as error:
            flash(str(error), "error")
    courses = CourseRepository().list_for_teacher(current_user.id)
    return render_template("teacher.html", courses=courses)


@main.post("/docente/cursos/<int:course_id>/sesion")
@roles_required("docente")
def create_attendance_session(course_id):
    try:
        attendance_session, raw_token = AttendanceService(
            session_minutes=current_app.config["QR_SESSION_MINUTES"]
        ).create_session(course_id, current_user.id)
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("main.teacher_dashboard"))
    tokens = session.get("teacher_qr_tokens", {})
    tokens[str(attendance_session.id)] = raw_token
    session["teacher_qr_tokens"] = tokens
    flash("QR de asistencia activo durante 15 minutos.", "success")
    return redirect(
        url_for("main.teacher_session", session_id=attendance_session.id)
    )


@main.get("/docente/sesiones/<int:session_id>")
@roles_required("docente")
def teacher_session(session_id):
    attendance_session = db.session.get(AttendanceSession, session_id)
    raw_token = session.get("teacher_qr_tokens", {}).get(str(session_id))
    if (
        not attendance_session
        or attendance_session.course.teacher_id != current_user.id
        or not raw_token
    ):
        abort(404)
    destination = urljoin(
        current_app.config["APP_BASE_URL"] or request.host_url,
        url_for("main.checkin", token=raw_token),
    )
    image = qrcode.make(destination)
    output = io.BytesIO()
    image.save(output, format="PNG")
    qr_data = base64.b64encode(output.getvalue()).decode("ascii")
    attendances = AttendanceRepository().list_for_course(
        attendance_session.course_id
    )
    session_end = attendance_session.expires_at
    if session_end.tzinfo is None:
        session_end = session_end.replace(tzinfo=timezone.utc)
    return render_template(
        "session.html",
        attendance_session=attendance_session,
        qr_data=qr_data,
        attendances=attendances,
        expired=session_end <= datetime.now(timezone.utc),
    )


@main.get("/alumno")
@roles_required("alumno")
def student_dashboard():
    attendances = AttendanceRepository().list_for_student(current_user.id)
    return render_template("student.html", attendances=attendances)


@main.get("/check-in")
@roles_required("alumno")
def checkin():
    return render_template("checkin.html", qr_token=request.args.get("token", ""))


@main.post("/api/asistencia")
@roles_required("alumno")
def record_attendance():
    try:
        attendance = AttendanceService().record_attendance(
            request.form.get("token", ""), current_user
        )
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("main.student_dashboard"))
    flash(
        f"Asistencia registrada para {attendance.session.course.name}.", "success"
    )
    return redirect(url_for("main.student_dashboard"))


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
            row.recorded_at.isoformat(),
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
            row.recorded_at.strftime("%d/%m/%Y %H:%M"),
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