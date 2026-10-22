from datetime import datetime, timezone

from app.repositories import (
    AttendanceRepository,
    CourseEnrollmentRepository,
    CourseRepository,
)


class AttendanceReportService:
    def __init__(self, attendance=None, courses=None, enrollments=None):
        self.attendance = attendance or AttendanceRepository()
        self.courses = courses or CourseRepository()
        self.enrollments = enrollments or CourseEnrollmentRepository()

    def session_report_data(self, session_id, timezone_name):
        attendance_session = self.attendance.find_session_by_id(session_id)
        if not attendance_session:
            return None, [], ""
        rows = []
        for item in self.attendance.list_for_session(session_id):
            student = item.student
            rows.append(
                {
                    "student_name": student.name if student else "Sin estudiante",
                    "carnet": student.carnet if student else "—",
                    "status": item.status,
                    "date": item.recorded_at.astimezone(timezone.utc).strftime("%d/%m/%Y") if item.recorded_at.tzinfo else item.recorded_at.strftime("%d/%m/%Y"),
                    "time": item.recorded_at.astimezone(timezone.utc).strftime("%H:%M") if item.recorded_at.tzinfo else item.recorded_at.strftime("%H:%M"),
                    "source": item.source,
                }
            )
        subtitle = (
            f"Curso {attendance_session.course.code} · "
            f"{attendance_session.course.schedule or 'Horario pendiente'}"
        )
        return attendance_session, rows, subtitle

    def session_status_data(self, attendance_session):
        records = self.attendance.list_for_session(attendance_session.id)
        records_by_student = {record.student_id: record for record in records}
        students = []
        for student in self.enrollments.list_students_for_course(
            attendance_session.course_id
        ):
            record = records_by_student.get(student.id)
            recorded_at = record.recorded_at if record else None
            if recorded_at and recorded_at.tzinfo is None:
                recorded_at = recorded_at.replace(tzinfo=timezone.utc)
            students.append(
                {
                    "id": student.id,
                    "status": record.status if record else "pendiente",
                    "source": record.source if record else None,
                    "recorded_at": recorded_at.isoformat() if recorded_at else None,
                }
            )
        present = sum(item.status == "presente" for item in records)
        justified = sum(item.status == "justificado" for item in records)
        absent = sum(item.status == "ausente" for item in records)
        return {
            "total": len(records),
            "present": present,
            "present_count": present,
            "justified": justified,
            "absent": absent,
            "students": students,
            "closed": attendance_session.closed_at is not None,
            "active": attendance_session.active,
        }

    def course_export_data(self, course_id, timezone_name):
        course = self.courses.get_by_id(course_id)
        if not course:
            return None, [], []
        records = self.attendance.list_for_course(course_id)
        csv_rows = []
        pdf_rows = []
        for item in records:
            student = item.student
            value = (
                student.carnet or "",
                student.name if student else "",
                student.email if student else "",
                course.name,
                course.code,
                course.teacher.name if course.teacher else "",
                item.recorded_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M") if item.recorded_at.tzinfo else item.recorded_at.strftime("%Y-%m-%d %H:%M"),
            )
            csv_rows.append(value)
            pdf_rows.append(list(value))
        return course, csv_rows, pdf_rows
