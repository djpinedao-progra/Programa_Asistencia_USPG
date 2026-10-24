import csv
import io

from flask import Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.controllers import main
from app.controllers.decorators import roles_required
from app.services import CourseEnrollmentService, CourseService, UserService
from app.services.course_service import (
    CLASSROOMS,
    WEEKDAYS,
    build_schedule,
    parse_schedule,
)
from app.views.reports.csv_builder import csv_safe as _csv_safe


def _schedule_from_form():
    return build_schedule(
        request.form.getlist("schedule_days"),
        request.form.get("start_time", ""),
        request.form.get("end_time", ""),
    )


def _teacher_id_from_form():
    try:
        return int(request.form.get("teacher_id", ""))
    except (TypeError, ValueError) as error:
        raise ValueError("Selecciona un docente válido para el curso.") from error


def _course_error_field(message):
    field_rules = (
        ("código", "code"),
        ("docente", "teacher_id"),
        ("modalidad", "location_type"),
        ("salón", "classroom"),
        ("ocupado", "classroom"),
        ("horario", "schedule_days"),
        ("día", "schedule_days"),
        ("alumno", "student_ids"),
    )
    normalized = message.casefold()
    return next(
        (field for fragment, field in field_rules if fragment in normalized),
        "name",
    )


def _render_admin_courses(form_data=None, field_errors=None, status=200):
    query = request.args.get("q", "").strip()
    normalized_query = query.casefold()
    teacher_id = request.args.get("docente", type=int)
    courses = CourseService().list_all()
    if normalized_query:
        courses = [
            course for course in courses
            if normalized_query in course.name.casefold()
            or normalized_query in course.code.casefold()
        ]
    if teacher_id:
        courses = [course for course in courses if course.teacher_id == teacher_id]
    user_service = UserService()
    teachers = user_service.list_by_role("docente")
    students = user_service.list_by_role("alumno")
    schedule_parts = {
        course.id: parse_schedule(course.schedule) for course in courses
    }
    classroom_occupancy = []
    for course in CourseService().list_all():
        parsed = parse_schedule(course.schedule)
        if (
            parsed
            and course.is_active
            and course.location_type == "presencial"
            and course.classroom in CLASSROOMS
        ):
            classroom_occupancy.append(
                {
                    "course_id": course.id,
                    "course_code": course.code,
                    "classroom": course.classroom,
                    "days": [day for day in WEEKDAYS if day in parsed["days"]],
                    "start": parsed["start"],
                    "end": parsed["end"],
                }
            )
    return render_template(
        "admin/admin_courses.html", courses=courses, teachers=teachers,
        students=students, query=query, selected_teacher=teacher_id,
        classrooms=CLASSROOMS, weekdays=WEEKDAYS,
        schedule_parts=schedule_parts, classroom_occupancy=classroom_occupancy,
        form_data=form_data or {}, field_errors=field_errors or {},
    ), status


@main.route("/admin/cursos/importar", methods=["GET", "POST"])
@roles_required("admin")
def admin_import_course_enrollments():
    if request.method == "GET":
        return render_template("admin/admin_course_import.html")

    if request.form.get("action") in {"import", "download-errors"}:
        return _process_enrollment_action(request.form.get("action"))
    return _preview_enrollment_file()


def _process_enrollment_action(action):
    course_codes = request.form.getlist("course_code")
    carnets = request.form.getlist("carnet")
    if len(course_codes) != len(carnets):
        abort(400, description="Las filas del archivo no tienen el mismo formato.")
    rows = CourseEnrollmentService().preview_rows(
        [
            (index + 2, code, carnet)
            for index, (code, carnet) in enumerate(zip(course_codes, carnets))
        ]
    )
    if action == "download-errors":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["line", "course_code", "carnet", "error"])
        writer.writerows(
            [
                row["line"],
                _csv_safe(row["course_code"]),
                _csv_safe(row["carnet"]),
                row["status"],
            ]
            for row in rows
            if not row["valid"] and row["status"] != "Ya está matriculado"
        )
        return Response(
            "\ufeff" + output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=matriculas-rechazadas.csv"
            },
        )
    enrollments = [
        (row["course_id"], row["student_id"]) for row in rows if row["valid"]
    ]
    try:
        added = CourseService().bulk_enroll(enrollments, actor_id=current_user.id)
    except ValueError as error:
        flash(str(error), "error")
        return render_template(
            "admin/admin_course_import.html", rows=rows, preview=False, imported=0
        )
    for row in rows:
        if row["valid"]:
            row["status"] = "Matriculado"
    return render_template(
        "admin/admin_course_import.html", rows=rows, preview=False, imported=added
    )


def _preview_enrollment_file():
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        flash("Selecciona un archivo CSV.", "error")
        return redirect(url_for("main.admin_import_course_enrollments"))
    content = uploaded_file.stream.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        flash("El archivo supera el límite de 2 MB.", "error")
        return redirect(url_for("main.admin_import_course_enrollments"))
    try:
        rows = CourseEnrollmentService().preview_csv(content)
    except (UnicodeDecodeError, csv.Error, ValueError) as error:
        flash(str(error) or "No se pudo leer el archivo CSV.", "error")
        return redirect(url_for("main.admin_import_course_enrollments"))
    return render_template(
        "admin/admin_course_import.html", rows=rows, preview=True, imported=0
    )


@main.get("/admin/cursos/importar/plantilla.csv")
@roles_required("admin")
def admin_course_import_template():
    output = io.StringIO(newline="")
    csv.writer(output).writerow(["course_code", "carnet"])
    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=plantilla-matriculas.csv"},
    )


@main.post("/admin/cursos")
@roles_required("admin")
def admin_create_course():
    try:
        teacher_id = _teacher_id_from_form()
        CourseService().create_course_for_admin(
            request.form.get("name", ""),
            request.form.get("code", ""),
            teacher_id,
            _schedule_from_form(),
            request.form.get("location_type", ""),
            request.form.get("classroom", ""),
            request.form.getlist("student_ids"),
            actor_id=current_user.id,
        )
        flash("Curso creado y asignaciones guardadas.", "success")
    except (ValueError, TypeError) as error:
        message = str(error) or "El docente seleccionado no es válido."
        form_data = request.form.to_dict()
        form_data["schedule_days"] = request.form.getlist("schedule_days")
        form_data["student_ids"] = request.form.getlist("student_ids")
        flash(message, "error")
        return _render_admin_courses(
            form_data, {_course_error_field(message): message}, status=400
        )
    return redirect(url_for("main.admin_courses"))


@main.post("/admin/cursos/<int:course_id>/asignaciones")
@roles_required("admin")
def admin_update_course(course_id):
    try:
        teacher_id = _teacher_id_from_form()
        CourseService().update_course_roster(
            course_id,
            teacher_id,
            _schedule_from_form(),
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


@main.get("/admin/cursos")
@roles_required("admin")
def admin_courses():
    return _render_admin_courses()


@main.post("/admin/cursos/<int:course_id>/estado")
@roles_required("admin")
def admin_toggle_course(course_id):
    course_service = CourseService()
    course = course_service.get_by_id(course_id)
    if not course:
        abort(404)
    try:
        course_service.set_course_active(
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
