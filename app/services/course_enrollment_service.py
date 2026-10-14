"""Reglas para matricular alumnos en cursos."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Attendance, AttendanceSession, Course, CourseEnrollment, User
from app.services.audit_service import AuditService


class CourseEnrollmentService:
    """Coordina matrículas y ausencias de sesiones ya cerradas."""

    @staticmethod
    def students_from_ids(student_ids):
        """Valida una lista de identificadores y devuelve alumnos existentes."""
        students = []
        for raw_student_id in set(student_ids):
            try:
                student_id = int(raw_student_id)
            except (TypeError, ValueError) as error:
                raise ValueError("La lista de alumnos no es válida.") from error
            student = db.session.get(User, student_id)
            if not student or student.role != "alumno":
                raise ValueError("Solo puedes asignar cuentas de alumno a un curso.")
            students.append(student)
        return students

    def bulk_enroll(self, enrollments, actor_id=None):
        """Agrega matrículas y registra faltas en sesiones cerradas."""
        new_pairs = set()
        for course_id, student_id in enrollments:
            course = db.session.get(Course, course_id)
            student = db.session.get(User, student_id)
            if not course or not student or student.role != "alumno":
                raise ValueError("Una de las matrículas seleccionadas ya no es válida.")
            new_pairs.add((course.id, student.id))

        existing_pairs = set(
            db.session.execute(
                select(CourseEnrollment.course_id, CourseEnrollment.student_id).where(
                    CourseEnrollment.course_id.in_({course_id for course_id, _ in new_pairs}),
                    CourseEnrollment.student_id.in_({student_id for _, student_id in new_pairs}),
                )
            ).all()
        ) if new_pairs else set()
        new_pairs -= existing_pairs
        if not new_pairs:
            return 0

        try:
            for course_id, student_id in new_pairs:
                db.session.add(
                    CourseEnrollment(course_id=course_id, student_id=student_id)
                )
                AuditService.record(
                    actor_id, "student_enrolled", "course_enrollment", None,
                    {"course_id": course_id, "student_id": student_id},
                )

            course_ids = {course_id for course_id, _ in new_pairs}
            closed_sessions = db.session.scalars(
                select(AttendanceSession).where(
                    AttendanceSession.course_id.in_(course_ids),
                    AttendanceSession.closed_at.is_not(None),
                )
            ).all()
            sessions_by_course = {}
            for attendance_session in closed_sessions:
                sessions_by_course.setdefault(attendance_session.course_id, []).append(
                    attendance_session
                )
            existing_attendance = set(
                db.session.execute(
                    select(Attendance.student_id, Attendance.session_id)
                    .join(AttendanceSession)
                    .where(AttendanceSession.course_id.in_(course_ids))
                ).all()
            )
            for course_id, student_id in new_pairs:
                for attendance_session in sessions_by_course.get(course_id, []):
                    if (student_id, attendance_session.id) not in existing_attendance:
                        db.session.add(
                            Attendance(
                                session_id=attendance_session.id,
                                student_id=student_id,
                                recorded_at=attendance_session.closed_at,
                                status="ausente",
                                source="cierre",
                            )
                        )
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            raise ValueError("No se pudieron guardar las matrículas.") from error
        return len(new_pairs)
