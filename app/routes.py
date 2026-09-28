import base64
import hashlib
import io
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urljoin

import qrcode
from sqlalchemy import or_, select
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
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from app import db
from app.models import Attendance, AttendanceSession, Course, CourseEnrollment, Notice, User
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
        "admin.html",
        users=users,
        courses=courses,
        attendances=attendances,
        teachers=[user for user in users if user.role == "docente"],
        students=[user for user in users if user.role == "alumno"],
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


@main.post("/admin/cursos")
@roles_required("admin")
def admin_create_course():
    try:
        teacher_id = int(request.form.get("teacher_id", ""))
        CourseService().create_course_for_admin(
            request.form.get("name", ""),
            request.form.get("code", ""),
            teacher_id,
            request.form.get("schedule", ""),
            request.form.get("location_type", ""),
            request.form.get("classroom", ""),
            request.form.getlist("student_ids"),
        )
        flash("Curso creado y asignaciones guardadas.", "success")
    except (ValueError, TypeError) as error:
        flash(str(error) or "El docente seleccionado no es válido.", "error")
    return redirect(url_for("main.admin_dashboard"))


@main.post("/admin/cursos/<int:course_id>/asignaciones")
@roles_required("admin")
def admin_update_course(course_id):
    try:
        teacher_id = int(request.form.get("teacher_id", ""))
        CourseService().update_course_roster(
            course_id,
            teacher_id,
            request.form.get("schedule", ""),
            request.form.get("location_type", ""),
            request.form.get("classroom", ""),
            request.form.getlist("student_ids"),
        )
        flash("Asignación del curso actualizada.", "success")
    except (ValueError, TypeError) as error:
        flash(str(error) or "El docente seleccionado no es válido.", "error")
    return redirect(url_for("main.admin_dashboard"))


def _teacher_course_metrics(course):
    sessions = db.session.scalars(
        select(AttendanceSession)
        .where(
            AttendanceSession.course_id == course.id,
            AttendanceSession.closed_at.is_not(None),
        )
        .order_by(AttendanceSession.closed_at.desc())
    ).all()
    enrollments = db.session.scalars(
        select(CourseEnrollment)
        .where(CourseEnrollment.course_id == course.id)
        .order_by(CourseEnrollment.student_id)
    ).all()
    records = db.session.scalars(
        select(Attendance)
        .join(AttendanceSession)
        .where(AttendanceSession.course_id == course.id)
    ).all()
    roster = [enrollment.student for enrollment in enrollments]
    if not roster:
        roster = list({record.student_id: record.student for record in records}.values())
    records_by_key = {
        (record.student_id, record.session_id): record for record in records
    }
    students = []
    for student in roster:
        present = absent = justified = 0
        for attendance_session in sessions:
            record = records_by_key.get((student.id, attendance_session.id))
            status = record.status if record else "ausente"
            present += status == "presente"
            absent += status == "ausente"
            justified += status == "justificado"
        percentage = round(present / len(sessions) * 100) if sessions else 0
        students.append(
            {
                "student": student,
                "present": present,
                "absent": absent,
                "justified": justified,
                "percentage": percentage,
            }
        )
    slots = len(sessions) * len(students)
    present_slots = sum(student["present"] for student in students)
    return {
        "course": course,
        "students": students,
        "student_count": len(students),
        "sessions_count": len(sessions),
        "average_percentage": round(present_slots / slots * 100) if slots else 0,
        "below_80": sum(student["percentage"] < 80 for student in students),
        "present_count": sum(student["present"] for student in students),
        "absence_count": sum(student["absent"] for student in students),
        "justified_count": sum(student["justified"] for student in students),
    }


def _course_roster(course_id):
    enrollments = db.session.scalars(
        select(CourseEnrollment).where(CourseEnrollment.course_id == course_id)
    ).all()
    if enrollments:
        return [enrollment.student for enrollment in enrollments]
    records = db.session.scalars(
        select(Attendance)
        .join(AttendanceSession)
        .where(AttendanceSession.course_id == course_id)
    ).all()
    return list({record.student_id: record.student for record in records}.values())


def _owned_attendance_session(session_id):
    attendance_session = db.session.get(AttendanceSession, session_id)
    if (
        not attendance_session
        or attendance_session.course.teacher_id != current_user.id
    ):
        abort(404)
    return attendance_session


def _save_teacher_qr_token(attendance_session):
    raw_token = secrets.token_urlsafe(32)
    attendance_session.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    attendance_session.expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=current_app.config["QR_SESSION_MINUTES"]
    )
    attendance_session.active = True
    attendance_session.closed_at = None
    db.session.commit()
    tokens = session.get("teacher_qr_tokens", {})
    tokens[str(attendance_session.id)] = raw_token
    session["teacher_qr_tokens"] = tokens
    return raw_token


def _create_low_attendance_notices(course):
    metrics = _teacher_course_metrics(course)
    existing_ids = set(
        db.session.scalars(
            select(Notice.student_id).where(
                Notice.course_id == course.id, Notice.kind == "automatic"
            )
        ).all()
    )
    for row in metrics["students"]:
        if row["percentage"] < 90 and row["student"].id not in existing_ids:
            db.session.add(
                Notice(
                    course_id=course.id,
                    student_id=row["student"].id,
                    sender_id=current_user.id,
                    message=(
                        f"Tu asistencia en {course.name} es de {row['percentage']}%. "
                        "El mínimo para examen final es 80%."
                    ),
                    kind="automatic",
                )
            )
    db.session.commit()


@main.get("/docente")
@roles_required("docente")
def teacher_dashboard():
    course_models = CourseRepository().list_for_teacher(current_user.id)
    course_metrics = [_teacher_course_metrics(course) for course in course_models]
    course_ids = [course.id for course in course_models]
    notices = []
    if course_ids:
        notices = db.session.scalars(
            select(Notice)
            .where(Notice.course_id.in_(course_ids))
            .order_by(Notice.created_at.desc())
            .limit(8)
        ).all()
    return render_template(
        "teacher.html",
        courses=course_models,
        course_metrics=course_metrics,
        notice_history=notices,
        total_enrollments=sum(course["student_count"] for course in course_metrics),
        total_sessions=sum(course["sessions_count"] for course in course_metrics),
        students_below_80=sum(course["below_80"] for course in course_metrics),
    )


@main.get("/docente/cursos/<int:course_id>")
@roles_required("docente")
def teacher_course(course_id):
    course = CourseRepository().get_for_teacher(course_id, current_user.id)
    if not course:
        abort(404)
    metrics = _teacher_course_metrics(course)
    sort_by = request.args.get("orden", "nombre")
    sort_keys = {
        "nombre": lambda row: row["student"].name.casefold(),
        "asistencias": lambda row: (-row["present"], row["student"].name.casefold()),
        "faltas": lambda row: (-row["absent"], row["student"].name.casefold()),
    }
    if sort_by not in sort_keys:
        sort_by = "nombre"
    metrics["students"].sort(key=sort_keys[sort_by])
    return render_template("teacher_course.html", **metrics, sort_by=sort_by)


@main.get("/docente/estudiantes")
@roles_required("docente")
def teacher_students():
    courses = CourseRepository().list_for_teacher(current_user.id)
    course_id = request.args.get("curso", type=int)
    selected_course = next(
        (course for course in courses if course.id == course_id), None
    )
    if course_id and not selected_course:
        abort(404)
    selected_courses = [selected_course] if selected_course else courses
    metrics = [_teacher_course_metrics(course) for course in selected_courses]
    students = []
    seen = set()
    for course_metrics in metrics:
        for row in course_metrics["students"]:
            student_id = row["student"].id
            if student_id not in seen:
                seen.add(student_id)
                students.append({**row, "course": course_metrics["course"]})
    students.sort(key=lambda row: row["student"].name.casefold())
    return render_template(
        "teacher_students.html",
        courses=courses,
        selected_course=selected_course,
        students=students,
    )


@main.get("/docente/historial")
@roles_required("docente")
def teacher_history():
    courses = CourseRepository().list_for_teacher(current_user.id)
    course_ids = [course.id for course in courses]
    records = []
    if course_ids:
        records = db.session.scalars(
            select(Attendance)
            .join(AttendanceSession)
            .where(AttendanceSession.course_id.in_(course_ids))
            .order_by(Attendance.recorded_at.desc())
            .limit(500)
        ).all()
    filters = {
        "curso": request.args.get("curso", ""),
        "fecha": request.args.get("fecha", ""),
        "estudiante": request.args.get("estudiante", "").strip(),
        "estado": request.args.get("estado", ""),
    }
    if filters["curso"].isdigit():
        records = [
            record for record in records
            if record.session.course_id == int(filters["curso"])
        ]
    if filters["fecha"]:
        records = [
            record for record in records
            if record.recorded_at.date().isoformat() == filters["fecha"]
        ]
    if filters["estudiante"]:
        needle = filters["estudiante"].casefold()
        records = [
            record for record in records
            if needle in record.student.name.casefold()
            or needle in (record.student.carnet or "").casefold()
        ]
    if filters["estado"] in {"presente", "ausente", "justificado"}:
        records = [record for record in records if record.status == filters["estado"]]
    return render_template(
        "teacher_history.html", courses=courses, records=records, filters=filters
    )


@main.post("/docente/historial/<int:attendance_id>")
@roles_required("docente")
def correct_attendance_record(attendance_id):
    attendance = db.session.get(Attendance, attendance_id)
    if not attendance or attendance.session.course.teacher_id != current_user.id:
        abort(404)
    status = request.form.get("status", "")
    if status not in {"presente", "ausente", "justificado"}:
        abort(400)
    attendance.status = status
    attendance.source = "manual"
    attendance.modified_by_id = current_user.id
    attendance.recorded_at = datetime.now(timezone.utc)
    db.session.commit()
    flash("Registro corregido manualmente.", "success")
    return redirect(url_for("main.teacher_history"))


@main.post("/docente/avisos")
@roles_required("docente")
def send_teacher_notice():
    course_id = request.form.get("course_id", type=int)
    student_id = request.form.get("student_id", type=int)
    course = CourseRepository().get_for_teacher(course_id, current_user.id)
    message = request.form.get("message", "").strip()
    if not course:
        abort(404)
    if not message or len(message) > 500:
        flash("Escribe un aviso de hasta 500 caracteres.", "error")
        return redirect(url_for("main.teacher_dashboard") + "#avisos")
    if student_id is not None:
        student = db.session.get(User, student_id)
        if not student or student not in _course_roster(course.id):
            abort(404)
    db.session.add(
        Notice(
            course_id=course.id,
            student_id=student_id,
            sender_id=current_user.id,
            message=message,
            kind="manual" if student_id else "broadcast",
        )
    )
    db.session.commit()
    flash(
        "Aviso enviado al estudiante." if student_id else "Aviso enviado al curso.",
        "success",
    )
    return redirect(url_for("main.teacher_dashboard") + "#avisos")


def _start_attendance_session(course_id):
    existing_session = db.session.scalar(
        select(AttendanceSession)
        .where(
            AttendanceSession.course_id == course_id,
            AttendanceSession.active.is_(True),
            AttendanceSession.closed_at.is_(None),
        )
        .order_by(AttendanceSession.created_at.desc())
    )
    if existing_session and existing_session.course.teacher_id == current_user.id:
        expiration = existing_session.expires_at
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        if expiration > datetime.now(timezone.utc):
            flash("Ya hay una asistencia abierta para ese curso.", "warning")
            return redirect(
                url_for("main.teacher_session", session_id=existing_session.id)
            )
        now = datetime.now(timezone.utc)
        existing_ids = set(
            db.session.scalars(
                select(Attendance.student_id).where(
                    Attendance.session_id == existing_session.id
                )
            ).all()
        )
        for student in _course_roster(course_id):
            if student.id not in existing_ids:
                db.session.add(
                    Attendance(
                        session_id=existing_session.id,
                        student_id=student.id,
                        recorded_at=now,
                        status="ausente",
                        source="cierre",
                        modified_by_id=current_user.id,
                    )
                )
        existing_session.active = False
        existing_session.closed_at = now
        db.session.commit()
        _create_low_attendance_notices(existing_session.course)
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
    flash("Asistencia iniciada. El código QR vence en 5 minutos.", "success")
    return redirect(
        url_for("main.teacher_session", session_id=attendance_session.id)
    )


@main.post("/docente/asistencia/iniciar")
@roles_required("docente")
def start_attendance_from_dashboard():
    try:
        course_id = int(request.form.get("course_id", ""))
    except ValueError:
        flash("Selecciona un curso válido.", "error")
        return redirect(url_for("main.teacher_dashboard") + "#tomar-asistencia")
    return _start_attendance_session(course_id)


@main.post("/docente/cursos/<int:course_id>/sesion")
@roles_required("docente")
def create_attendance_session(course_id):
    return _start_attendance_session(course_id)


@main.get("/docente/sesiones/<int:session_id>")
@roles_required("docente")
def teacher_session(session_id):
    attendance_session = _owned_attendance_session(session_id)
    raw_token = session.get("teacher_qr_tokens", {}).get(str(session_id))
    if not raw_token and attendance_session.active and not attendance_session.closed_at:
        raw_token = _save_teacher_qr_token(attendance_session)
    session_end = attendance_session.expires_at
    if session_end.tzinfo is None:
        session_end = session_end.replace(tzinfo=timezone.utc)
    expired = session_end <= datetime.now(timezone.utc) or not attendance_session.active
    qr_data = None
    if raw_token and not expired:
        destination = urljoin(
            current_app.config["APP_BASE_URL"] or request.host_url,
            url_for("main.checkin", token=raw_token),
        )
        image = qrcode.make(destination)
        output = io.BytesIO()
        image.save(output, format="PNG")
        qr_data = base64.b64encode(output.getvalue()).decode("ascii")
    attendances = db.session.scalars(
        select(Attendance).where(Attendance.session_id == session_id)
    ).all()
    attendance_by_student = {
        attendance.student_id: attendance for attendance in attendances
    }
    return render_template(
        "session.html",
        attendance_session=attendance_session,
        qr_data=qr_data,
        attendances=attendances,
        students=_course_roster(attendance_session.course_id),
        attendance_by_student=attendance_by_student,
        expired=expired,
        expires_timestamp=int(session_end.timestamp()),
        closed=attendance_session.closed_at is not None,
    )


@main.post("/docente/sesiones/<int:session_id>/renovar")
@roles_required("docente")
def renew_attendance_qr(session_id):
    attendance_session = _owned_attendance_session(session_id)
    if not attendance_session.active or attendance_session.closed_at:
        flash("La asistencia está cerrada.", "error")
        return redirect(url_for("main.teacher_session", session_id=session_id))
    _save_teacher_qr_token(attendance_session)
    flash("Nuevo QR activo durante 5 minutos.", "success")
    return redirect(url_for("main.teacher_session", session_id=session_id))


@main.get("/docente/sesiones/<int:session_id>/estado")
@roles_required("docente")
def attendance_session_status(session_id):
    attendance_session = _owned_attendance_session(session_id)
    records = {
        record.student_id: record
        for record in db.session.scalars(
            select(Attendance).where(Attendance.session_id == session_id)
        ).all()
    }
    students = []
    for student in _course_roster(attendance_session.course_id):
        record = records.get(student.id)
        students.append(
            {
                "id": student.id,
                "name": student.name,
                "carnet": student.carnet or "—",
                "status": record.status if record else "pendiente",
                "source": record.source if record else "",
                "recorded_at": (
                    record.recorded_at.isoformat() if record else None
                ),
            }
        )
    return jsonify(
        {
            "students": students,
            "active": attendance_session.active,
            "closed": attendance_session.closed_at is not None,
            "present_count": sum(row["status"] == "presente" for row in students),
        }
    )


@main.post("/docente/sesiones/<int:session_id>/estudiantes/<int:student_id>")
@roles_required("docente")
def set_session_attendance(session_id, student_id):
    attendance_session = _owned_attendance_session(session_id)
    if not attendance_session.active or attendance_session.closed_at:
        abort(409)
    student = db.session.get(User, student_id)
    if not student or student not in _course_roster(attendance_session.course_id):
        abort(404)
    status = request.form.get("status", "")
    if status not in {"presente", "ausente", "justificado"}:
        abort(400)
    attendance = db.session.scalar(
        select(Attendance).where(
            Attendance.session_id == session_id,
            Attendance.student_id == student_id,
        )
    )
    now = datetime.now(timezone.utc)
    if attendance is None:
        attendance = Attendance(
            session_id=session_id,
            student_id=student_id,
            recorded_at=now,
        )
        db.session.add(attendance)
    attendance.status = status
    attendance.source = "manual"
    attendance.modified_by_id = current_user.id
    attendance.recorded_at = now
    db.session.commit()
    return redirect(url_for("main.teacher_session", session_id=session_id))


@main.post("/docente/sesiones/<int:session_id>/cerrar")
@roles_required("docente")
def close_attendance_session(session_id):
    attendance_session = _owned_attendance_session(session_id)
    if attendance_session.closed_at:
        flash("La asistencia ya estaba cerrada.", "warning")
        return redirect(url_for("main.teacher_session", session_id=session_id))
    now = datetime.now(timezone.utc)
    existing_ids = set(
        db.session.scalars(
            select(Attendance.student_id).where(Attendance.session_id == session_id)
        ).all()
    )
    for student in _course_roster(attendance_session.course_id):
        if student.id not in existing_ids:
            db.session.add(
                Attendance(
                    session_id=session_id,
                    student_id=student.id,
                    recorded_at=now,
                    status="ausente",
                    source="cierre",
                    modified_by_id=current_user.id,
                )
            )
    attendance_session.active = False
    attendance_session.closed_at = now
    db.session.commit()
    _create_low_attendance_notices(attendance_session.course)
    flash("Asistencia cerrada; las faltas pendientes quedaron registradas.", "success")
    return redirect(url_for("main.teacher_session", session_id=session_id))


@main.get("/alumno")
@roles_required("alumno")
def student_dashboard():
    attendances = AttendanceRepository().list_for_student(current_user.id)
    course_ids = {attendance.session.course_id for attendance in attendances}
    course_ids.update(
        db.session.scalars(
            select(CourseEnrollment.course_id).where(
                CourseEnrollment.student_id == current_user.id
            )
        ).all()
    )
    sessions = []
    if course_ids:
        sessions = db.session.scalars(
            select(AttendanceSession)
            .where(AttendanceSession.course_id.in_(course_ids))
            .order_by(AttendanceSession.created_at.desc())
        ).all()

    attendance_by_session = {
        attendance.session_id: attendance for attendance in attendances
    }
    sessions = [
        attendance_session
        for attendance_session in sessions
        if attendance_session.closed_at is not None
        or attendance_session.id in attendance_by_session
    ]
    student_courses = db.session.scalars(
        select(Course).where(Course.id.in_(course_ids))
    ).all() if course_ids else []
    course_progress = {
        course.id: {
            "course": course,
            "total_sessions": 0,
            "attended_count": 0,
            "attendance_records": [],
        }
        for course in student_courses
    }
    for attendance_session in sessions:
        course = attendance_session.course
        progress = course_progress.setdefault(
            course.id,
            {
                "course": course,
                "total_sessions": 0,
                "attended_count": 0,
                "attendance_records": [],
            },
        )
        progress["total_sessions"] += 1
        attendance = attendance_by_session.get(attendance_session.id)
        if attendance:
            progress["attended_count"] += attendance.status == "presente"
            progress["attendance_records"].append(attendance)

    courses = sorted(course_progress.values(), key=lambda item: item["course"].name)
    for course in courses:
        course["absence_count"] = course["total_sessions"] - course["attended_count"]
        course["percentage"] = round(
            course["attended_count"] / course["total_sessions"] * 100
        ) if course["total_sessions"] else 0

    total_sessions = sum(course["total_sessions"] for course in courses)
    total_attended = sum(course["attended_count"] for course in courses)
    overall_percentage = round(total_attended / total_sessions * 100) if total_sessions else 0
    notices = [course for course in courses if course["percentage"] < 90]
    received_notices = []
    if course_ids:
        received_notices = db.session.scalars(
            select(Notice)
            .where(
                Notice.course_id.in_(course_ids),
                or_(
                    Notice.student_id == current_user.id,
                    Notice.student_id.is_(None),
                ),
            )
            .order_by(Notice.created_at.desc())
            .limit(20)
        ).all()

    return render_template(
        "student.html",
        attendances=attendances,
        recent_attendances=attendances[:6],
        courses=courses,
        total_sessions=total_sessions,
        total_attended=total_attended,
        total_absences=total_sessions - total_attended,
        overall_percentage=overall_percentage,
        notices=notices,
        received_notices=received_notices,
    )


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