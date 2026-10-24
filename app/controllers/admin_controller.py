from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.controllers import main
from app.controllers.decorators import roles_required
from app.services import AuditService, CourseService, UserService
from app.services.metrics_service import (
    admin_attendance_overview_data,
    admin_dashboard_data,
    admin_history_data,
    admin_student_summaries,
)


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
                actor_id=current_user.id,
            )
            flash("Usuario creado correctamente.", "success")
            return redirect(url_for("main.admin_dashboard"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template(
        "admin/admin.html",
        **admin_dashboard_data(current_app.config["APP_TIMEZONE"]),
    )


@main.post("/admin/usuarios/<int:user_id>/carnet")
@roles_required("admin")
def update_student_carnet(user_id):
    try:
        UserService().assign_student_carnet(
            user_id, request.form.get("carnet", ""), actor_id=current_user.id
        )
        flash("Carnet actualizado.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("main.admin_dashboard"))


@main.get("/admin/estudiantes")
@roles_required("admin")
def admin_students():
    query = request.args.get("q", "").strip()
    normalized_query = query.casefold()
    course_id = request.args.get("curso", type=int)
    courses = CourseService().list_all()
    if course_id and not any(course.id == course_id for course in courses):
        abort(404)
    students = admin_student_summaries(
        course_id=course_id,
        timezone_name=current_app.config["APP_TIMEZONE"],
    )
    if normalized_query:
        students = [
            row for row in students
            if normalized_query in row["student"].name.casefold()
            or normalized_query in row["student"].email.casefold()
            or normalized_query in (row["student"].carnet or "").casefold()
        ]
    return render_template(
        "admin/admin_students.html", students=students, courses=courses,
        query=query, selected_course=course_id,
    )


@main.get("/admin/docentes")
@roles_required("admin")
def admin_teachers():
    query = request.args.get("q", "").strip()
    normalized_query = query.casefold()
    teachers = UserService().list_by_role("docente")
    if normalized_query:
        teachers = [
            teacher for teacher in teachers
            if normalized_query in teacher.name.casefold()
            or normalized_query in teacher.email.casefold()
        ]
    return render_template("admin/admin_teachers.html", teachers=teachers, query=query)


@main.route("/admin/usuarios/<int:user_id>/perfil", methods=["GET", "POST"])
@roles_required("admin")
def admin_user_profile(user_id):
    user = UserService().find_by_id(user_id)
    if not user or user.role not in {"alumno", "docente"}:
        abort(404)
    if request.method == "POST":
        try:
            UserService().update_profile(
                user.id,
                request.form.get("name", ""),
                request.form.get("email", ""),
                request.form.get("carnet", ""),
                actor_id=current_user.id,
            )
            flash("Perfil actualizado.", "success")
            return redirect(url_for("main.admin_user_profile", user_id=user.id))
        except ValueError as error:
            flash(str(error), "error")
    profile_courses = (
        user.courses if user.role == "docente"
        else [enrollment.course for enrollment in user.course_enrollments]
    )
    return render_template(
        "admin/admin_profile.html", user=user, profile_courses=profile_courses
    )


@main.post("/admin/usuarios/<int:user_id>/restablecer-contrasena")
@roles_required("admin")
def admin_reset_user_password(user_id):
    try:
        UserService().admin_reset_password(
            user_id,
            request.form.get("new_password", ""),
            request.form.get("confirm_password", ""),
            actor_id=current_user.id,
        )
        flash("Contraseña restablecida. Comunica la clave al usuario por un canal seguro.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("main.admin_user_profile", user_id=user_id))


@main.get("/admin/asistencias")
@roles_required("admin")
def admin_attendance_overview():
    course_id = request.args.get("curso", type=int)
    session_date = request.args.get("fecha", "")
    query = request.args.get("estudiante", "").strip().casefold()
    risk_filter = request.args.get("riesgo", "")
    courses = CourseService().list_all()
    if course_id and not any(course.id == course_id for course in courses):
        abort(404)
    students = admin_attendance_overview_data(
        course_id,
        session_date,
        query,
        risk_filter,
        current_app.config["APP_TIMEZONE"],
    )
    return render_template(
        "admin/admin_attendance.html", students=students, courses=courses,
        selected_course=course_id, session_date=session_date,
        query=query, risk_filter=risk_filter,
    )


@main.get("/admin/historial")
@roles_required("admin")
def admin_history():
    course_id = request.args.get("curso", type=int)
    teacher_id = request.args.get("docente", type=int)
    session_date = request.args.get("fecha", "")
    courses = CourseService().list_all()
    teachers = UserService().list_by_role("docente")
    requested_page = max(1, request.args.get("page", 1, type=int))
    sessions, total, pages, page = admin_history_data(
        course_id,
        teacher_id,
        session_date,
        requested_page,
        current_app.config["APP_TIMEZONE"],
    )
    return render_template(
        "admin/admin_history.html", sessions=sessions, courses=courses,
        teachers=teachers, selected_course=course_id,
        selected_teacher=teacher_id, session_date=session_date,
        page=page, pages=pages, total=total,
    )


@main.get("/admin/auditoria")
@roles_required("admin")
def admin_audit_log():
    service = AuditService()
    total = service.count_all()
    pages = max(1, (total + 49) // 50)
    page = min(max(1, request.args.get("page", 1, type=int)), pages)
    entries = service.list_page(page, page_size=50)
    return render_template(
        "admin/admin_audit.html", entries=entries, page=page, pages=pages, total=total
    )
