from sqlalchemy import func, select

from app.extensions import db
from app.models import (
    Attendance,
    AttendanceSession,
    Course,
    CourseEnrollment,
    Notice,
    User,
)
from app.repositories import CourseRepository
from app.utils.time_utils import local_date_utc_bounds


def _local_date_bounds_or_none(value, timezone_name):
    if not value:
        return None
    try:
        return local_date_utc_bounds(value, timezone_name)
    except ValueError:
        return None


def admin_student_summaries(course_id=None, session_date=None, timezone_name="America/Guatemala"):
    students = db.session.scalars(
        select(User).where(User.role == "alumno").order_by(User.name)
    ).all()
    courses = CourseRepository().list_all()
    course_by_id = {course.id: course for course in courses}
    course_ids_by_student = {student.id: set() for student in students}
    enrollments = db.session.execute(
        select(CourseEnrollment.student_id, CourseEnrollment.course_id)
    ).all()
    for student_id, enrolled_course_id in enrollments:
        course_ids_by_student.setdefault(student_id, set()).add(enrolled_course_id)
    historical_courses = db.session.execute(
        select(Attendance.student_id, AttendanceSession.course_id)
        .join(AttendanceSession)
        .distinct()
    ).all()
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
    if relevant_course_ids:
        session_statement = select(AttendanceSession).where(
            AttendanceSession.course_id.in_(relevant_course_ids),
            AttendanceSession.closed_at.is_not(None),
        )
        if session_date:
            bounds = _local_date_bounds_or_none(session_date, timezone_name)
            if bounds:
                start, end = bounds
                session_statement = session_statement.where(
                    AttendanceSession.created_at >= start,
                    AttendanceSession.created_at < end,
                )
            else:
                session_statement = session_statement.where(AttendanceSession.id == -1)
        sessions = db.session.scalars(
            session_statement.order_by(AttendanceSession.created_at.desc())
        ).all()
    session_ids = {item.id for item in sessions}
    status_by_student_course = {}
    if session_ids:
        status_rows = db.session.execute(
            select(
                Attendance.student_id,
                AttendanceSession.course_id,
                Attendance.status,
                func.count(),
            )
            .join(AttendanceSession)
            .where(Attendance.session_id.in_(session_ids))
            .group_by(Attendance.student_id, AttendanceSession.course_id, Attendance.status)
        ).all()
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
        percentage = round(present / total * 100) if total else 0
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


def admin_session_summaries(
    course_id=None, teacher_id=None, session_date=None, page=None, page_size=25, timezone_name="America/Guatemala"
):
    statement = select(AttendanceSession).join(Course)
    conditions = []
    if course_id:
        conditions.append(AttendanceSession.course_id == course_id)
    if teacher_id:
        conditions.append(Course.teacher_id == teacher_id)
    if session_date:
        bounds = _local_date_bounds_or_none(session_date, timezone_name)
        if bounds:
            start, end = bounds
            conditions.extend(
                [AttendanceSession.created_at >= start, AttendanceSession.created_at < end]
            )
        else:
            conditions.append(AttendanceSession.id == -1)
    if conditions:
        statement = statement.where(*conditions)
    total = db.session.scalar(
        select(func.count(AttendanceSession.id)).select_from(AttendanceSession)
        .join(Course).where(*conditions)
    )
    statement = statement.order_by(AttendanceSession.created_at.desc())
    if page is not None:
        statement = statement.offset((page - 1) * page_size).limit(page_size)
    sessions = db.session.scalars(statement).all()
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


def preview_enrollment_rows(input_rows):
    courses = {
        course.code.casefold(): course
        for course in CourseRepository().list_all()
    }
    students = {
        student.carnet: student
        for student in db.session.scalars(
            select(User).where(User.role == "alumno", User.carnet.is_not(None))
        ).all()
    }
    existing_enrollments = set(
        db.session.execute(select(CourseEnrollment.course_id, CourseEnrollment.student_id)).all()
    )
    seen = set()
    results = []
    for line_number, raw_code, raw_carnet in input_rows:
        code = (raw_code or "").strip().upper()
        carnet = (raw_carnet or "").strip()
        course = courses.get(code.casefold())
        student = students.get(carnet)
        valid = False
        if not code or not carnet:
            status = "Falta código de curso o carnet"
        elif not course:
            status = "Curso no encontrado"
        elif not course.is_active:
            status = "El curso está deshabilitado"
        elif not student:
            status = "Alumno no encontrado"
        elif (course.id, student.id) in seen:
            status = "Duplicado en el archivo"
        elif (course.id, student.id) in existing_enrollments:
            status = "Ya está matriculado"
        else:
            status = "Listo para matricular"
            valid = True
        if course and student:
            seen.add((course.id, student.id))
        results.append(
            {
                "line": line_number,
                "course_code": code,
                "carnet": carnet,
                "status": status,
                "valid": valid,
                "course_id": course.id if course else None,
                "student_id": student.id if student else None,
            }
        )
    return results


def teacher_course_metrics(course):
    sessions = db.session.scalars(
        select(AttendanceSession)
        .where(
            AttendanceSession.course_id == course.id,
            AttendanceSession.closed_at.is_not(None),
        )
        .order_by(AttendanceSession.closed_at.desc())
    ).all()
    roster = db.session.scalars(
        select(User)
        .join(CourseEnrollment, CourseEnrollment.student_id == User.id)
        .where(CourseEnrollment.course_id == course.id)
        .order_by(User.id)
    ).all()
    if not roster:
        historical_student_ids = db.session.scalars(
            select(Attendance.student_id)
            .join(AttendanceSession)
            .where(AttendanceSession.course_id == course.id)
            .distinct()
        ).all()
        if historical_student_ids:
            roster = db.session.scalars(
                select(User)
                .where(User.id.in_(historical_student_ids))
                .order_by(User.id)
            ).all()
    counts_by_student = {}
    if sessions:
        counts = db.session.execute(
            select(Attendance.student_id, Attendance.status, func.count())
            .join(AttendanceSession)
            .where(
                AttendanceSession.course_id == course.id,
                AttendanceSession.closed_at.is_not(None),
            )
            .group_by(Attendance.student_id, Attendance.status)
        ).all()
        for student_id, status, count in counts:
            counts_by_student.setdefault(student_id, {})[status] = count
    students = []
    for student in roster:
        status_counts = counts_by_student.get(student.id, {})
        present = status_counts.get("presente", 0)
        justified = status_counts.get("justificado", 0)
        absent = max(0, len(sessions) - present - justified)
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


def course_roster(course_id):
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


def create_low_attendance_notices(course, actor_id):
    metrics = teacher_course_metrics(course)
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
                    sender_id=actor_id,
                    message=(
                        f"Tu asistencia en {course.name} es de {row['percentage']}%. "
                        "El mínimo para examen final es 80%."
                    ),
                    kind="automatic",
                )
            )
    db.session.commit()
