from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.controllers import main
from app.controllers.decorators import roles_required
from app.services import AttendanceService, CourseService, NoticeService
from app.services.metrics_service import teacher_course_metrics


@main.get("/docente")
@roles_required("docente")
def teacher_dashboard():
    course_models = CourseService().list_for_teacher(current_user.id)
    course_metrics = [teacher_course_metrics(course) for course in course_models]
    course_ids = [course.id for course in course_models]
    notices = []
    if course_ids:
        notices = NoticeService().list_for_courses(course_ids, limit=8)
    return render_template(
        "teacher/teacher.html",
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
    course = CourseService().get_for_teacher(course_id, current_user.id)
    if not course:
        abort(404)
    metrics = teacher_course_metrics(course)
    sort_by = request.args.get("orden", "nombre")
    sort_keys = {
        "nombre": lambda row: row["student"].name.casefold(),
        "asistencias": lambda row: (-row["present"], row["student"].name.casefold()),
        "faltas": lambda row: (-row["absent"], row["student"].name.casefold()),
    }
    if sort_by not in sort_keys:
        sort_by = "nombre"
    metrics["students"].sort(key=sort_keys[sort_by])
    return render_template("teacher/teacher_course.html", **metrics, sort_by=sort_by)


@main.get("/docente/estudiantes")
@roles_required("docente")
def teacher_students():
    courses = CourseService().list_for_teacher(current_user.id)
    course_id = request.args.get("curso", type=int)
    selected_course = next(
        (course for course in courses if course.id == course_id), None
    )
    if course_id and not selected_course:
        abort(404)
    selected_courses = [selected_course] if selected_course else courses
    metrics = [teacher_course_metrics(course) for course in selected_courses]
    students = []
    for course_metrics in metrics:
        for row in course_metrics["students"]:
            students.append({**row, "course": course_metrics["course"]})
    students.sort(
        key=lambda row: (row["student"].name.casefold(), row["course"].name.casefold())
    )
    return render_template(
        "teacher/teacher_students.html",
        courses=courses,
        selected_course=selected_course,
        students=students,
    )


@main.get("/docente/historial")
@roles_required("docente")
def teacher_history():
    courses = CourseService().list_for_teacher(current_user.id)
    course_ids = [course.id for course in courses]
    filters = {
        "curso": request.args.get("curso", ""),
        "fecha": request.args.get("fecha", ""),
        "estudiante": request.args.get("estudiante", "").strip(),
        "estado": request.args.get("estado", ""),
    }
    total, pages, page, records = AttendanceService().teacher_history_data(
        course_ids,
        filters,
        request.args.get("page", 1, type=int),
        current_app.config["APP_TIMEZONE"],
    )
    return render_template(
        "teacher/teacher_history.html", courses=courses, records=records, filters=filters,
        page=page, pages=pages, total=total,
    )


@main.post("/docente/historial/<int:attendance_id>")
@roles_required("docente")
def correct_attendance_record(attendance_id):
    status = request.form.get("status", "")
    try:
        corrected = AttendanceService().correct_attendance_record(
            attendance_id, current_user.id, status
        )
    except ValueError:
        abort(400)
    if not corrected:
        abort(404)
    flash("Registro corregido manualmente.", "success")
    return redirect(url_for("main.teacher_history"))


@main.post("/docente/avisos")
@roles_required("docente")
def send_teacher_notice():
    course_id = request.form.get("course_id", type=int)
    student_id = request.form.get("student_id", type=int)
    course = CourseService().get_for_teacher(course_id, current_user.id)
    message = request.form.get("message", "").strip()
    if not course:
        abort(404)
    if not message or len(message) > 500:
        flash("Escribe un aviso de hasta 500 caracteres.", "error")
        return redirect(url_for("main.teacher_dashboard") + "#avisos")
    if not NoticeService().create_manual_notice(
        course, student_id, current_user.id, message
    ):
        abort(404)
    flash(
        "Aviso enviado al estudiante." if student_id else "Aviso enviado al curso.",
        "success",
    )
    return redirect(url_for("main.teacher_dashboard") + "#avisos")


