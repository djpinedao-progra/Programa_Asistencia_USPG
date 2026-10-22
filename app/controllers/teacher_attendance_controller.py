import base64
from datetime import datetime, timezone
from urllib.parse import urljoin

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user

from app.controllers import main
from app.controllers.decorators import roles_required
from app.services import AttendanceReportService, AttendanceService
from app.services.metrics_service import (
    course_roster,
    create_low_attendance_notices,
)
from app.views.reports.qr_builder import build_qr_png


def _owned_attendance_session(session_id):
    attendance_session = AttendanceService().find_session_by_id(session_id)
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
    raw_token = AttendanceService(
        session_minutes=current_app.config["QR_SESSION_MINUTES"]
    ).renew_token(attendance_session)
    tokens = session.get("teacher_qr_tokens", {})
    tokens[str(attendance_session.id)] = raw_token
    session["teacher_qr_tokens"] = tokens
    return raw_token


def _create_low_attendance_notices(course):
    return create_low_attendance_notices(course, current_user.id)


def _start_attendance_session(course_id):
    existing_session = AttendanceService().find_open_session_for_course(
        course_id
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
        AttendanceService().close_session(existing_session, current_user.id)
        _remove_teacher_qr_token(existing_session.id)
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
    minutes = current_app.config["QR_SESSION_MINUTES"]
    flash(
        f"Asistencia iniciada. El código QR vence en {minutes} minutos.",
        "success",
    )
    return redirect(
        url_for("main.teacher_session", session_id=attendance_session.id)
    )


def _teacher_session_context(session_id):
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
    attendances = AttendanceService().list_for_session(session_id)
    return {
        "attendance_session": attendance_session,
        "qr_data": qr_data,
        "attendances": attendances,
        "students": course_roster(attendance_session.course_id),
        "attendance_by_student": {
            attendance.student_id: attendance for attendance in attendances
        },
        "expired": expired,
        "expires_timestamp": int(session_end.timestamp()),
        "qr_session_minutes": current_app.config["QR_SESSION_MINUTES"],
        "closed": attendance_session.closed_at is not None,
    }


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
    return render_template(
        "teacher/session.html",
        **_teacher_session_context(session_id),
    )


@main.post("/docente/sesiones/<int:session_id>/renovar")
@roles_required("docente")
def renew_attendance_qr(session_id):
    attendance_session = _owned_attendance_session(session_id)
    if not attendance_session.active or attendance_session.closed_at:
        flash("La asistencia está cerrada.", "error")
        return redirect(url_for("main.teacher_session", session_id=session_id))
    _save_teacher_qr_token(attendance_session)
    minutes = current_app.config["QR_SESSION_MINUTES"]
    flash(f"Nuevo QR activo durante {minutes} minutos.", "success")
    return redirect(url_for("main.teacher_session", session_id=session_id))


@main.get("/docente/sesiones/<int:session_id>/estado")
@roles_required("docente")
def attendance_session_status(session_id):
    attendance_session = _owned_attendance_session(session_id)
    return jsonify(
        AttendanceReportService().session_status_data(attendance_session)
    )


@main.post("/docente/sesiones/<int:session_id>/estudiantes/<int:student_id>")
@roles_required("docente")
def set_session_attendance(session_id, student_id):
    attendance_session = _owned_attendance_session(session_id)
    if not attendance_session.active or attendance_session.closed_at:
        abort(409)
    attendance_service = AttendanceService()
    if not attendance_service.is_course_student(
        attendance_session.course_id, student_id
    ):
        abort(404)
    status = request.form.get("status", "")
    if status not in {"presente", "ausente", "justificado"}:
        abort(400)
    attendance_service.set_manual_attendance(
        session_id, student_id, current_user.id, status
    )
    return redirect(url_for("main.teacher_session", session_id=session_id))


@main.post("/docente/sesiones/<int:session_id>/cerrar")
@roles_required("docente")
def close_attendance_session(session_id):
    attendance_session = _owned_attendance_session(session_id)
    if attendance_session.closed_at:
        flash("La asistencia ya estaba cerrada.", "warning")
        return redirect(url_for("main.teacher_session", session_id=session_id))
    AttendanceService().close_session(attendance_session, current_user.id)
    _remove_teacher_qr_token(attendance_session.id)
    _create_low_attendance_notices(attendance_session.course)
    flash("Asistencia cerrada; las faltas pendientes quedaron registradas.", "success")
    return redirect(url_for("main.teacher_session", session_id=session_id))
