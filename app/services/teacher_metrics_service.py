from sqlalchemy import func, select

from app.extensions import db
from app.models import Attendance, AttendanceSession, CourseEnrollment, Notice, User


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
