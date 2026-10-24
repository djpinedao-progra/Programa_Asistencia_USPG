from app.models import Notice
from app.repositories import (
    AttendanceMetricsRepository,
    AttendanceRepository,
    CourseEnrollmentRepository,
    NoticeRepository,
    UserRepository,
)
from app.services.attendance_calculation_service import (
    attendance_percentage,
    exam_eligibility,
)


def teacher_course_metrics(course):
    metrics_repository = AttendanceMetricsRepository()
    sessions = metrics_repository.list_closed_sessions_for_course(course.id)
    roster = CourseEnrollmentRepository().list_students_for_course(course.id)
    if not roster:
        historical_student_ids = (
            metrics_repository.list_historical_student_ids_for_course(course.id)
        )
        if historical_student_ids:
            roster = UserRepository().list_by_ids(historical_student_ids)
    counts_by_student = {}
    if sessions:
        counts = metrics_repository.list_status_counts_for_course(course.id)
        for student_id, status, count in counts:
            counts_by_student.setdefault(student_id, {})[status] = count
    students = []
    for student in roster:
        status_counts = counts_by_student.get(student.id, {})
        present = status_counts.get("presente", 0)
        justified = status_counts.get("justificado", 0)
        absent = max(0, len(sessions) - present - justified)
        percentage = attendance_percentage(present, justified, len(sessions))
        exam = exam_eligibility(absent)
        students.append(
            {
                "student": student,
                "present": present,
                "absent": absent,
                "justified": justified,
                "percentage": percentage,
                "has_sessions": bool(sessions),
                "exam_eligible": exam["eligible"],
                "absences_remaining": exam["absences_remaining"],
                "exam_risk": exam["risk"],
            }
        )
    slots = len(sessions) * len(students)
    attended_slots = sum(
        student["present"] + student["justified"] for student in students
    )
    return {
        "course": course,
        "students": students,
        "student_count": len(students),
        "sessions_count": len(sessions),
        "average_percentage": attendance_percentage(attended_slots, 0, slots),
        "exam_ineligible": sum(
            student["has_sessions"] and not student["exam_eligible"]
            for student in students
        ),
        "present_count": sum(student["present"] for student in students),
        "absence_count": sum(student["absent"] for student in students),
        "justified_count": sum(student["justified"] for student in students),
    }


def create_low_attendance_notices(course, actor_id):
    metrics = teacher_course_metrics(course)
    if not metrics["sessions_count"]:
        return
    notice_repository = NoticeRepository()
    existing_ids = set(notice_repository.list_automatic_student_ids(course.id))
    notices = []
    for row in metrics["students"]:
        if row["exam_risk"] != "ninguno" and row["student"].id not in existing_ids:
            situation = (
                "Ya no tienes derecho a examen final por acumular tres faltas."
                if not row["exam_eligible"]
                else "Te queda una falta antes de perder el derecho a examen final."
            )
            notices.append(
                Notice(
                    course_id=course.id,
                    student_id=row["student"].id,
                    sender_id=actor_id,
                    message=(
                        f"Llevas {row['absent']} faltas en {course.name}. "
                        f"{situation}"
                    ),
                    kind="automatic",
                )
            )
    notice_repository.add_all(notices)


def course_roster(course_id):
    enrollments = CourseEnrollmentRepository().list_for_course(course_id)
    if enrollments:
        return [enrollment.student for enrollment in enrollments]
    records = AttendanceRepository().list_for_course_without_order(course_id)
    return list({record.student_id: record.student for record in records}.values())
