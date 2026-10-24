from app.repositories import (
    AttendanceMetricsRepository,
    CourseRepository,
    UserRepository,
)
from app.utils.time_utils import local_date_utc_bounds
from app.services.attendance_calculation_service import attendance_percentage


def admin_dashboard_data(timezone_name="America/Guatemala"):
    users = UserRepository().list_all()
    courses = CourseRepository().list_all()
    student_summaries = admin_student_summaries(
        timezone_name=timezone_name
    )
    session_summaries = admin_session_summaries(
        timezone_name=timezone_name
    )[:6]
    return {
        "users": users,
        "courses": courses,
        "teachers": [user for user in users if user.role == "docente"],
        "students": [user for user in users if user.role == "alumno"],
        "at_risk_students": sum(
            row["risk"] != "ninguno" for row in student_summaries
        ),
        "recent_sessions": session_summaries,
    }


def admin_attendance_overview_data(
    course_id, session_date, query, risk_filter, timezone_name
):
    students = admin_student_summaries(
        course_id, session_date or None, timezone_name
    )
    if query:
        students = [
            row
            for row in students
            if query in row["student"].name.casefold()
            or query in (row["student"].carnet or "").casefold()
        ]
    if risk_filter in {"alto", "medio", "ninguno"}:
        students = [row for row in students if row["risk"] == risk_filter]
    return students


def admin_history_data(
    course_id, teacher_id, session_date, requested_page, timezone_name
):
    sessions, total = admin_session_summaries(
        course_id,
        teacher_id,
        session_date or None,
        page=requested_page,
        timezone_name=timezone_name,
    )
    pages = max(1, (total + 24) // 25)
    page = min(requested_page, pages)
    if page != requested_page:
        sessions, total = admin_session_summaries(
            course_id,
            teacher_id,
            session_date or None,
            page=page,
            timezone_name=timezone_name,
        )
    return sessions, total, pages, page


def admin_report_pdf_data(course, summaries):
    return {
        "rows": [
            {
                **row,
                "student_name": row["student"].name,
                "student_carnet": row["student"].carnet,
            }
            for row in summaries
        ],
        "title": "Reporte de asistencia" if not course else f"Reporte {course.name}",
        "subtitle": (
            "Todos los cursos"
            if not course
            else f"Curso {course.code} · {course.schedule or 'Horario pendiente'}"
        ),
        "filename": f"reporte-asistencia-{course.code if course else 'general'}.pdf",
    }


def _local_date_bounds_or_none(value, timezone_name):
    if not value:
        return None
    try:
        return local_date_utc_bounds(value, timezone_name)
    except ValueError:
        return None


def admin_session_summaries(
    course_id=None, teacher_id=None, session_date=None, page=None, page_size=25, timezone_name="America/Guatemala"
):
    date_bounds = None
    invalid_date = False
    if session_date:
        date_bounds = _local_date_bounds_or_none(session_date, timezone_name)
        invalid_date = date_bounds is None
    sessions, total = AttendanceMetricsRepository().list_admin_session_page(
        course_id,
        teacher_id,
        date_bounds,
        invalid_date,
        page,
        page_size,
    )
    summaries = []
    for attendance_session in sessions:
        records = attendance_session.attendances
        assigned_count = len(attendance_session.course.enrollments)
        if not assigned_count:
            assigned_count = len({record.student_id for record in records})
        present_count = sum(record.status == "presente" for record in records)
        summaries.append(
            {
                "session": attendance_session,
                "course": attendance_session.course,
                "teacher": attendance_session.course.teacher,
                "present": present_count,
                "total": assigned_count,
            }
        )
    return (summaries, total) if page is not None else summaries


def admin_student_summaries(course_id=None, session_date=None, timezone_name="America/Guatemala"):
    students = UserRepository().list_by_role("alumno")
    courses = CourseRepository().list_all()
    course_by_id = {course.id: course for course in courses}
    course_ids_by_student = {student.id: set() for student in students}
    attendance_repository = AttendanceMetricsRepository()
    enrollments, historical_courses = attendance_repository.list_student_course_links()
    for student_id, enrolled_course_id in enrollments:
        course_ids_by_student.setdefault(student_id, set()).add(enrolled_course_id)
    for student_id, historical_course_id in historical_courses:
        course_ids_by_student.setdefault(student_id, set()).add(historical_course_id)
    if course_id:
        students = [
            student
            for student in students
            if course_id in course_ids_by_student.get(student.id, set())
        ]
    relevant_course_ids = {
        selected_id
        for student in students
        for selected_id in course_ids_by_student.get(student.id, set())
        if selected_id in course_by_id and (not course_id or selected_id == course_id)
    }
    sessions = []
    date_bounds = None
    invalid_date = False
    if session_date:
        date_bounds = _local_date_bounds_or_none(session_date, timezone_name)
        invalid_date = date_bounds is None
    if relevant_course_ids:
        sessions = attendance_repository.list_closed_sessions_for_courses(
            relevant_course_ids, date_bounds, invalid_date
        )
    session_ids = {item.id for item in sessions}
    status_by_student_course = {}
    if session_ids:
        status_rows = attendance_repository.list_status_counts_for_sessions(
            session_ids
        )
        for student_id, course_id_for_status, status, count in status_rows:
            status_by_student_course.setdefault(
                (student_id, course_id_for_status), {}
            )[status] = count
    total_sessions_by_course = {}
    for attendance_session in sessions:
        total_sessions_by_course[attendance_session.course_id] = (
            total_sessions_by_course.get(attendance_session.course_id, 0) + 1
        )
    summaries = []
    for student in students:
        student_course_ids = course_ids_by_student.get(student.id, set())
        if course_id:
            student_course_ids = student_course_ids & {course_id}
        total = sum(
            total_sessions_by_course.get(student_course_id, 0)
            for student_course_id in student_course_ids
        )
        present = sum(
            status_by_student_course.get((student.id, student_course_id), {}).get(
                "presente", 0
            )
            for student_course_id in student_course_ids
        )
        justified = sum(
            status_by_student_course.get((student.id, student_course_id), {}).get(
                "justificado", 0
            )
            for student_course_id in student_course_ids
        )
        absent = max(0, total - present - justified)
        percentage = attendance_percentage(present, justified, total)
        risk = "alto" if total and percentage < 60 else (
            "medio" if total and percentage < 80 else "ninguno"
        )
        assigned_courses = [
            course_by_id[item]
            for item in sorted(student_course_ids)
            if item in course_by_id
        ]
        summaries.append(
            {
                "student": student,
                "courses": assigned_courses,
                "course_names": ", ".join(course.code for course in assigned_courses),
                "present": present,
                "absent": absent,
                "justified": justified,
                "total_sessions": total,
                "percentage": percentage,
                "risk": risk,
            }
        )
    return summaries
