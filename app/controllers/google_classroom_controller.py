import hmac

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from app.controllers import main
from app.controllers.decorators import roles_required
from app.services import GoogleClassroomService
from app.services.course_service import CLASSROOMS, WEEKDAYS, build_schedule
from app.services.google_classroom_service import (
    GoogleClassroomConfigurationError,
    suggested_course_code,
)


def _service():
    if not GoogleClassroomService.enabled():
        abort(404)
    return GoogleClassroomService(current_user.id)


@main.get("/admin/google")
@roles_required("admin")
def admin_google_classroom():
    service = _service()
    connection = service.connection()
    errors = service.configuration_errors()
    courses = []
    if connection and not errors:
        try:
            courses = service.list_courses()
        except ValueError as error:
            flash(str(error), "error")
    return render_template(
        "admin/admin_google_classroom.html",
        connection=connection,
        configuration_errors=errors,
        courses=courses,
    )


@main.get("/admin/google/connect")
@roles_required("admin")
def admin_google_connect():
    service = _service()
    try:
        authorization_url, state, code_verifier = service.authorization_url()
    except GoogleClassroomConfigurationError as error:
        flash(str(error), "error")
        return redirect(url_for("main.admin_google_classroom"))
    session["google_oauth_state"] = state
    session["google_oauth_code_verifier"] = code_verifier
    return redirect(authorization_url)


@main.get("/admin/google/callback")
@roles_required("admin")
def admin_google_callback():
    service = _service()
    expected_state = session.pop("google_oauth_state", "")
    code_verifier = session.pop("google_oauth_code_verifier", "")
    received_state = request.args.get("state", "")
    if (
        not expected_state
        or not code_verifier
        or not received_state
        or not hmac.compare_digest(expected_state, received_state)
    ):
        abort(
            400,
            description=(
                "La respuesta de Google no superó la validación de seguridad."
            ),
        )
    if request.args.get("error"):
        flash("Google no autorizó la conexión.", "error")
        return redirect(url_for("main.admin_google_classroom"))
    code = request.args.get("code", "")
    if not code:
        abort(400, description="Google no envió el código de autorización.")
    try:
        profile = service.save_authorization_code(code, received_state, code_verifier)
    except (ValueError, GoogleClassroomConfigurationError) as error:
        flash(str(error), "error")
    else:
        email = profile.get("emailAddress", "la cuenta seleccionada")
        flash(f"Google Classroom conectado con {email}.", "success")
    return redirect(url_for("main.admin_google_classroom"))


@main.post("/admin/google/disconnect")
@roles_required("admin")
def admin_google_disconnect():
    service = _service()
    if service.disconnect():
        flash("La cuenta de Google Classroom fue desconectada.", "success")
    else:
        flash("No había una cuenta de Google conectada.", "error")
    return redirect(url_for("main.admin_google_classroom"))


@main.get("/admin/google/cursos/<classroom_course_id>")
@roles_required("admin")
def admin_google_course_preview(classroom_course_id):
    service = _service()
    try:
        course = service.course_preview(classroom_course_id)
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("main.admin_google_classroom"))
    return render_template(
        "admin/admin_google_course_preview.html",
        course=course,
        suggested_code=suggested_course_code(course),
        classrooms=CLASSROOMS,
        weekdays=WEEKDAYS,
    )


@main.post("/admin/google/cursos/<classroom_course_id>/importar")
@roles_required("admin")
def admin_google_course_import(classroom_course_id):
    service = _service()
    try:
        schedule = build_schedule(
            request.form.getlist("schedule_days"),
            request.form.get("start_time", ""),
            request.form.get("end_time", ""),
        )
        result = service.import_course(
            classroom_course_id,
            request.form.get("code", ""),
            schedule,
            request.form.get("location_type", ""),
            request.form.get("classroom", ""),
            current_user.id,
        )
    except ValueError as error:
        flash(str(error), "error")
        return redirect(
            url_for(
                "main.admin_google_course_preview",
                classroom_course_id=classroom_course_id,
            )
        )
    flash(
        f"{result['course'].name} sincronizado con "
        f"{result['students_imported']} alumnos. "
        f"{result['missing_carnet']} requieren carnet.",
        "success",
    )
    if result["issues"]:
        flash(
            f"{len(result['issues'])} perfiles no pudieron importarse; "
            "revisa sus dominios o roles.",
            "error",
        )
    return redirect(url_for("main.admin_courses"))
