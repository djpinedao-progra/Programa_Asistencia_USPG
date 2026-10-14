from sqlalchemy import or_, select

from app.extensions import db
from app.models import AttendanceSession, Course, CourseEnrollment, Notice
from app.repositories import AttendanceRepository


def student_dashboard_data(student_id, page_number=1):
    attendances = AttendanceRepository().list_for_student(student_id)
    history_total = len(attendances)
    history_pages = max(1, (history_total + 24) // 25)
    history_page = min(max(1, page_number), history_pages)
    history_attendances = attendances[(history_page - 1) * 25 : history_page * 25]
    course_ids = {attendance.session.course_id for attendance in attendances}
    course_ids.update(
        db.session.scalars(
            select(CourseEnrollment.course_id).where(
                CourseEnrollment.student_id == student_id
            )
        ).all()
    )
    sessions = []
    if course_ids:
        sessions = db.session.scalars(
            select(AttendanceSession)
            .where(AttendanceSession.course_id.in_(course_ids))
            .order_by(AttendanceSession.created_at.desc())
        ).all()
    attendance_by_session = {
        attendance.session_id: attendance for attendance in attendances
    }
    sessions = [
        attendance_session
        for attendance_session in sessions
        if attendance_session.closed_at is not None
        or attendance_session.id in attendance_by_session
    ]
    student_courses = (
        db.session.scalars(select(Course).where(Course.id.in_(course_ids))).all()
        if course_ids
        else []
    )
    course_progress = {
        course.id: {
            "course": course,
            "total_sessions": 0,
            "attended_count": 0,
            "absence_count": 0,
            "justified_count": 0,
            "attendance_records": [],
        }
        for course in student_courses
    }
    for attendance_session in sessions:
        course = attendance_session.course
        progress = course_progress.setdefault(
            course.id,
            {
                "course": course,
                "total_sessions": 0,
                "attended_count": 0,
                "absence_count": 0,
                "justified_count": 0,
                "attendance_records": [],
            },
        )
        progress["total_sessions"] += 1
        attendance = attendance_by_session.get(attendance_session.id)
        if attendance:
            progress["attended_count"] += attendance.status == "presente"
            progress["absence_count"] += attendance.status == "ausente"
            progress["justified_count"] += attendance.status == "justificado"
            progress["attendance_records"].append(attendance)
    courses = sorted(course_progress.values(), key=lambda item: item["course"].name)
    for course in courses:
        course["percentage"] = (
            round(course["attended_count"] / course["total_sessions"] * 100)
            if course["total_sessions"]
            else 0
        )
    total_sessions = sum(course["total_sessions"] for course in courses)
    total_attended = sum(course["attended_count"] for course in courses)
    overall_percentage = round(total_attended / total_sessions * 100) if total_sessions else 0
    notices = [course for course in courses if course["percentage"] < 90]
    received_notices = []
    if course_ids:
        received_notices = db.session.scalars(
            select(Notice)
            .where(
                Notice.course_id.in_(course_ids),
                or_(
                    Notice.student_id == student_id,
                    Notice.student_id.is_(None),
                ),
            )
            .order_by(Notice.created_at.desc())
            .limit(20)
        ).all()
    return {
        "attendances": attendances,
        "history_attendances": history_attendances,
        "history_total": history_total,
        "history_page": history_page,
        "history_pages": history_pages,
        "recent_attendances": attendances[:6],
        "courses": courses,
        "total_sessions": total_sessions,
        "total_attended": total_attended,
        "total_absences": sum(course["absence_count"] for course in courses),
        "overall_percentage": overall_percentage,
        "notices": notices,
        "received_notices": received_notices,
    }
