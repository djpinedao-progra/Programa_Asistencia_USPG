from app.models import AttendanceSession, Course, Notice
from app.repositories import (
    AttendanceRepository,
    CourseEnrollmentRepository,
    NoticeRepository,
)


def student_dashboard_data(student_id, page_number=1):
    attendance_repository = AttendanceRepository()
    enrollment_repository = CourseEnrollmentRepository()
    attendances = attendance_repository.list_for_student(student_id)
    history_total = len(attendances)
    history_pages = max(1, (history_total + 24) // 25)
    history_page = min(max(1, page_number), history_pages)
    history_attendances = attendances[(history_page - 1) * 25 : history_page * 25]
    course_ids = {attendance.session.course_id for attendance in attendances}
    course_ids.update(enrollment_repository.list_course_ids_for_student(student_id))
    sessions = attendance_repository.list_sessions_for_courses(course_ids)
    attendance_by_session = {
        attendance.session_id: attendance for attendance in attendances
    }
    sessions = [
        attendance_session
        for attendance_session in sessions
        if attendance_session.closed_at is not None
        or attendance_session.id in attendance_by_session
    ]
    student_courses = enrollment_repository.list_courses(course_ids)
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
    received_notices = NoticeRepository().list_for_student_courses(
        course_ids, student_id, limit=20
    )
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
