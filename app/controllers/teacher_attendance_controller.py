from app.controllers import main
from app.controllers.decorators import roles_required
from app.controllers._support import *
from app.controllers._support import _course_roster
from app.views.reports.qr_builder import build_qr_png


def _owned_attendance_session(session_id):
    attendance_session = db.session.get(AttendanceSession, session_id)
    if (
        not attendance_session
        or attendance_session.course.teacher_id != current_user.id
    ):
        abort(404)
    return attendance_session


def _remove_teacher_qr_token(session_id):
    tokens = session.get("teacher_qr_tokens", {})
    if str(session_id) in tokens:
        tokens.pop(str(session_id), None)
        if tokens:
            session["teacher_qr_tokens"] = tokens
        else:
            session.pop("teacher_qr_tokens", None)


def _save_teacher_qr_token(attendance_session):
    raw_token = secrets.token_urlsafe(32)
    attendance_session.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    attendance_session.expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=min(current_app.config["QR_SESSION_MINUTES"], 1)
    )
    attendance_session.active = True
    attendance_session.closed_at = None
    db.session.commit()
    tokens = session.get("teacher_qr_tokens", {})
    tokens[str(attendance_session.id)] = raw_token
    session["teacher_qr_tokens"] = tokens
    return raw_token


def _create_low_attendance_notices(course):
    return create_low_attendance_notices(course, current_user.id)


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
        _remove_teacher_qr_token(existing_session.id)
        db.session.commit()
        _create_low_attendance_notices(existing_session.course)
    try:
        attendance_session, raw_token = AttendanceService(
            session_minutes=min(current_app.config["QR_SESSION_MINUTES"], 1)
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
        qr_data = base64.b64encode(build_qr_png(destination)).decode("ascii")
    attendances = db.session.scalars(
        select(Attendance).where(Attendance.session_id == session_id)
    ).all()
    attendance_by_student = {
        attendance.student_id: attendance for attendance in attendances
    }
    return render_template(
        "teacher/session.html",
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
                    utc_isoformat(record.recorded_at) if record else None
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
    previous_status = attendance.status if attendance else None
    if attendance is None:
        attendance = Attendance(
            session_id=session_id,
            student_id=student_id,
            recorded_at=now,
        )
        db.session.add(attendance)
        db.session.flush()
    else:
        attendance.modified_at = now
    attendance.status = status
    attendance.source = "manual"
    attendance.modified_by_id = current_user.id
    AuditService.record(
        current_user.id, "attendance_corrected", "attendance", attendance.id,
        {
            "student_id": student.id,
            "session_id": session_id,
            "previous_status": previous_status,
            "status": status,
        },
    )
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
    _remove_teacher_qr_token(attendance_session.id)
    db.session.commit()
    _create_low_attendance_notices(attendance_session.course)
    flash("Asistencia cerrada; las faltas pendientes quedaron registradas.", "success")
    return redirect(url_for("main.teacher_session", session_id=session_id))
