from app.controllers import main
from app.controllers.decorators import roles_required
from app.controllers._support import *
from app.controllers._support import _admin_student_summaries, _admin_session_summaries, _csv_safe, _preview_enrollment_rows, _local_date_bounds_or_none


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
    users = UserRepository().list_all()
    courses = CourseRepository().list_all()
    student_summaries = _admin_student_summaries()
    session_summaries = _admin_session_summaries()[:6]
    return render_template(
        "admin.html",
        users=users,
        courses=courses,
        teachers=[user for user in users if user.role == "docente"],
        students=[user for user in users if user.role == "alumno"],
        at_risk_students=sum(row["risk"] != "ninguno" for row in student_summaries),
        recent_sessions=session_summaries,
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
            actor_id=current_user.id,
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
            request.form.get("is_active") == "on",
            request.form.get("name", ""),
            request.form.get("code", ""),
            actor_id=current_user.id,
        )
        flash("Asignación del curso actualizada.", "success")
    except (ValueError, TypeError) as error:
        flash(str(error) or "El docente seleccionado no es válido.", "error")
    return redirect(url_for("main.admin_dashboard"))


@main.get("/admin/estudiantes")
@roles_required("admin")
def admin_students():
    query = request.args.get("q", "").strip().casefold()
    course_id = request.args.get("curso", type=int)
    courses = CourseRepository().list_all()
    if course_id and not any(course.id == course_id for course in courses):
        abort(404)
    students = _admin_student_summaries(course_id=course_id)
    if query:
        students = [
            row for row in students
            if query in row["student"].name.casefold()
            or query in row["student"].email.casefold()
            or query in (row["student"].carnet or "").casefold()
        ]
    return render_template(
        "admin_students.html", students=students, courses=courses,
        query=query, selected_course=course_id,
    )


@main.get("/admin/docentes")
@roles_required("admin")
def admin_teachers():
    query = request.args.get("q", "").strip().casefold()
    teachers = db.session.scalars(
        select(User).where(User.role == "docente").order_by(User.name)
    ).all()
    if query:
        teachers = [
            teacher for teacher in teachers
            if query in teacher.name.casefold() or query in teacher.email.casefold()
        ]
    return render_template("admin_teachers.html", teachers=teachers, query=query)


@main.route("/admin/usuarios/<int:user_id>/perfil", methods=["GET", "POST"])
@roles_required("admin")
def admin_user_profile(user_id):
    user = db.session.get(User, user_id)
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
        "admin_profile.html", user=user, profile_courses=profile_courses
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


@main.post("/admin/cursos/<int:course_id>/estado")
@roles_required("admin")
def admin_toggle_course(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        abort(404)
    try:
        CourseService.set_course_active(
            course_id,
            request.form.get("is_active") == "on",
            actor_id=current_user.id,
        )
        flash(
            "Curso habilitado para el docente." if course.is_active
            else "Curso deshabilitado; las sesiones abiertas se cerraron.",
            "success",
        )
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("main.admin_teachers"))


@main.get("/admin/cursos")
@roles_required("admin")
def admin_courses():
    query = request.args.get("q", "").strip().casefold()
    teacher_id = request.args.get("docente", type=int)
    courses = CourseRepository().list_all()
    if query:
        courses = [
            course for course in courses
            if query in course.name.casefold() or query in course.code.casefold()
        ]
    if teacher_id:
        courses = [course for course in courses if course.teacher_id == teacher_id]
    teachers = db.session.scalars(
        select(User).where(User.role == "docente").order_by(User.name)
    ).all()
    students = db.session.scalars(
        select(User).where(User.role == "alumno").order_by(User.name)
    ).all()
    return render_template(
        "admin_courses.html", courses=courses, teachers=teachers,
        students=students, query=query, selected_teacher=teacher_id,
    )






@main.get("/admin/asistencias")
@roles_required("admin")
def admin_attendance_overview():
    course_id = request.args.get("curso", type=int)
    session_date = request.args.get("fecha", "")
    query = request.args.get("estudiante", "").strip().casefold()
    risk_filter = request.args.get("riesgo", "")
    courses = CourseRepository().list_all()
    if course_id and not any(course.id == course_id for course in courses):
        abort(404)
    students = _admin_student_summaries(course_id, session_date or None)
    if query:
        students = [
            row for row in students
            if query in row["student"].name.casefold()
            or query in (row["student"].carnet or "").casefold()
        ]
    if risk_filter in {"alto", "medio", "ninguno"}:
        students = [row for row in students if row["risk"] == risk_filter]
    return render_template(
        "admin_attendance.html", students=students, courses=courses,
        selected_course=course_id, session_date=session_date,
        query=query, risk_filter=risk_filter,
    )


@main.get("/admin/historial")
@roles_required("admin")
def admin_history():
    course_id = request.args.get("curso", type=int)
    teacher_id = request.args.get("docente", type=int)
    session_date = request.args.get("fecha", "")
    courses = CourseRepository().list_all()
    teachers = db.session.scalars(
        select(User).where(User.role == "docente").order_by(User.name)
    ).all()
    requested_page = max(1, request.args.get("page", 1, type=int))
    sessions, total = _admin_session_summaries(
        course_id, teacher_id, session_date or None, page=requested_page
    )
    pages = max(1, (total + 24) // 25)
    page = min(requested_page, pages)
    if page != requested_page:
        sessions, total = _admin_session_summaries(
            course_id, teacher_id, session_date or None, page=page
        )
    return render_template(
        "admin_history.html", sessions=sessions, courses=courses,
        teachers=teachers, selected_course=course_id,
        selected_teacher=teacher_id, session_date=session_date,
        page=page, pages=pages, total=total,
    )


@main.get("/admin/auditoria")
@roles_required("admin")
def admin_audit_log():
    total = db.session.scalar(select(func.count(AuditLog.id))) or 0
    pages = max(1, (total + 49) // 50)
    page = min(max(1, request.args.get("page", 1, type=int)), pages)
    entries = db.session.scalars(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * 50)
        .limit(50)
    ).all()
    return render_template(
        "admin_audit.html", entries=entries, page=page, pages=pages, total=total
    )
