from app.controllers import main
from app.controllers.decorators import roles_required
from app.controllers._support import *
from app.controllers._support import _teacher_course_metrics, _local_date_bounds_or_none


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
    for course_metrics in metrics:
        for row in course_metrics["students"]:
            students.append({**row, "course": course_metrics["course"]})
    students.sort(
        key=lambda row: (row["student"].name.casefold(), row["course"].name.casefold())
    )
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
    filters = {
        "curso": request.args.get("curso", ""),
        "fecha": request.args.get("fecha", ""),
        "estudiante": request.args.get("estudiante", "").strip(),
        "estado": request.args.get("estado", ""),
    }
    conditions = [AttendanceSession.course_id.in_(course_ids)] if course_ids else []
    if filters["curso"]:
        if filters["curso"].isdigit() and int(filters["curso"]) in course_ids:
            conditions.append(AttendanceSession.course_id == int(filters["curso"]))
        else:
            conditions.append(AttendanceSession.course_id == -1)
    if filters["fecha"]:
        bounds = _local_date_bounds_or_none(filters["fecha"])
        if bounds:
            start, end = bounds
            conditions.extend(
                [Attendance.recorded_at >= start, Attendance.recorded_at < end]
            )
        else:
            conditions.append(Attendance.id == -1)
    if filters["estudiante"]:
        needle = f"%{filters['estudiante']}%"
        conditions.append(
            or_(User.name.ilike(needle), User.carnet.ilike(needle))
        )
    if filters["estado"] in {"presente", "ausente", "justificado"}:
        conditions.append(Attendance.status == filters["estado"])
    total = db.session.scalar(
        select(func.count(Attendance.id)).select_from(Attendance)
        .join(AttendanceSession).join(User, Attendance.student_id == User.id)
        .where(*conditions)
    ) if conditions else 0
    pages = max(1, (total + 24) // 25)
    page = min(max(1, request.args.get("page", 1, type=int)), pages)
    records = db.session.scalars(
        select(Attendance).join(AttendanceSession)
        .join(User, Attendance.student_id == User.id)
        .where(*conditions)
        .order_by(Attendance.recorded_at.desc(), Attendance.id.desc())
        .offset((page - 1) * 25).limit(25)
    ).all() if conditions else []
    return render_template(
        "teacher_history.html", courses=courses, records=records, filters=filters,
        page=page, pages=pages, total=total,
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
    previous_status = attendance.status
    attendance.status = status
    attendance.source = "manual"
    attendance.modified_by_id = current_user.id
    attendance.modified_at = datetime.now(timezone.utc)
    AuditService.record(
        current_user.id, "attendance_corrected", "attendance", attendance.id,
        {
            "student_id": attendance.student_id,
            "session_id": attendance.session_id,
            "previous_status": previous_status,
            "status": status,
        },
    )
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













