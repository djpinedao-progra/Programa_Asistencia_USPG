from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Attendance, AttendanceSession, Course, CourseEnrollment, User
from app.repositories import CourseRepository
from app.services.audit_service import AuditService


class CourseService:
    def __init__(self, courses=None):
        self.courses = courses or CourseRepository()

    def create_course(self, name, code, teacher_id):
        name, code = name.strip(), code.strip().upper()
        if not name or not code:
            raise ValueError("El nombre y el código del curso son obligatorios.")
        course = Course(name=name, code=code, teacher_id=teacher_id)
        try:
            return self.courses.add(course)
        except IntegrityError as error:
            db.session.rollback()
            raise ValueError("Ese código de curso ya está registrado.") from error

    def create_course_for_admin(
        self, name, code, teacher_id, schedule, location_type, classroom,
        student_ids, actor_id=None,
    ):
        name, code = name.strip(), code.strip().upper()
        schedule, classroom = schedule.strip(), classroom.strip()
        if not name or not code or not schedule:
            raise ValueError("Completa el nombre, código y horario del curso.")
        teacher = db.session.get(User, teacher_id)
        if not teacher or teacher.role != "docente":
            raise ValueError("Selecciona un docente válido para el curso.")
        if location_type not in {"presencial", "virtual"}:
            raise ValueError("Selecciona una modalidad válida.")
        if location_type == "presencial" and not classroom:
            raise ValueError("Indica el salón del curso presencial.")
        if location_type == "virtual":
            classroom = "Virtual"
        students = self._students_from_ids(student_ids)
        if db.session.scalar(select(Course).where(Course.code == code)):
            raise ValueError("Ese código de curso ya está registrado.")
        course = Course(
            name=name,
            code=code,
            teacher_id=teacher.id,
            schedule=schedule,
            location_type=location_type,
            classroom=classroom,
        )
        course.enrollments = [
            CourseEnrollment(student=student) for student in students
        ]
        try:
            db.session.add(course)
            db.session.flush()
            AuditService.record(
                actor_id, "course_created", "course", course.id,
                {
                    "code": course.code,
                    "teacher_id": teacher.id,
                    "student_ids": sorted(student.id for student in students),
                },
            )
            db.session.commit()
            return course
        except IntegrityError as error:
            db.session.rollback()
            raise ValueError("No se pudo guardar el curso. Revisa su código.") from error

    def update_course_roster(
        self,
        course_id,
        teacher_id,
        schedule,
        location_type,
        classroom,
        student_ids,
        is_active=True,
        name=None,
        code=None,
        actor_id=None,
    ):
        course = db.session.get(Course, course_id)
        if not course:
            raise ValueError("No se encontró el curso.")
        teacher = db.session.get(User, teacher_id)
        if not teacher or teacher.role != "docente":
            raise ValueError("Selecciona un docente válido para el curso.")
        schedule, classroom = schedule.strip(), classroom.strip()
        if not schedule:
            raise ValueError("El horario del curso es obligatorio.")
        if location_type not in {"presencial", "virtual"}:
            raise ValueError("Selecciona una modalidad válida.")
        if location_type == "presencial" and not classroom:
            raise ValueError("Indica el salón del curso presencial.")
        students = self._students_from_ids(student_ids)
        name = (name if name is not None else course.name).strip()
        code = (code if code is not None else course.code).strip().upper()
        if not name or not code:
            raise ValueError("El nombre y el código del curso son obligatorios.")
        duplicate_code = db.session.scalar(
            select(Course).where(Course.code == code, Course.id != course.id)
        )
        if duplicate_code:
            raise ValueError("Ese código de curso ya está registrado.")
        previous_values = {
            "name": course.name,
            "code": course.code,
            "teacher_id": course.teacher_id,
            "schedule": course.schedule,
            "location_type": course.location_type,
            "classroom": course.classroom,
            "is_active": course.is_active,
        }
        previous_student_ids = {enrollment.student_id for enrollment in course.enrollments}
        course.name = name
        course.code = code
        course.teacher_id = teacher.id
        course.schedule = schedule
        course.location_type = location_type
        course.classroom = "Virtual" if location_type == "virtual" else classroom
        course.is_active = bool(is_active)
        selected_ids = {student.id for student in students}
        existing_ids = {enrollment.student_id for enrollment in course.enrollments}
        for enrollment in list(course.enrollments):
            if enrollment.student_id not in selected_ids:
                db.session.delete(enrollment)
        for student in students:
            if student.id not in existing_ids:
                course.enrollments.append(CourseEnrollment(student=student))
        try:
            course_sessions = db.session.scalars(
                select(AttendanceSession).where(
                    AttendanceSession.course_id == course.id
                )
            ).all()
            closed_sessions = []
            for attendance_session in course_sessions:
                if not course.is_active and attendance_session.closed_at is None:
                    attendance_session.active = False
                    attendance_session.closed_at = datetime.now(timezone.utc)
                if attendance_session.closed_at is not None:
                    closed_sessions.append(attendance_session)
            existing_attendance = set(
                db.session.execute(
                    select(Attendance.student_id, Attendance.session_id)
                    .join(AttendanceSession)
                    .where(AttendanceSession.course_id == course.id)
                ).all()
            )
            for student in students:
                for attendance_session in closed_sessions:
                    if (student.id, attendance_session.id) not in existing_attendance:
                        db.session.add(
                            Attendance(
                                session_id=attendance_session.id,
                                student_id=student.id,
                                recorded_at=attendance_session.closed_at,
                                status="ausente",
                                source="cierre",
                            )
                        )
            changed_fields = [
                field for field, old_value in previous_values.items()
                if old_value != getattr(course, field)
            ]
            added_student_ids = sorted(selected_ids - previous_student_ids)
            removed_student_ids = sorted(previous_student_ids - selected_ids)
            if changed_fields or added_student_ids or removed_student_ids:
                AuditService.record(
                    actor_id, "course_updated", "course", course.id,
                    {
                        "changed_fields": changed_fields,
                        "added_student_ids": added_student_ids,
                        "removed_student_ids": removed_student_ids,
                    },
                )
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            raise ValueError("No se pudieron actualizar las asignaciones.") from error
        return course

    def bulk_enroll(self, enrollments, actor_id=None):
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

    @staticmethod
    def set_course_active(course_id, is_active, actor_id=None):
        course = db.session.get(Course, course_id)
        if not course:
            raise ValueError("No se encontró el curso.")
        previous_active = course.is_active
        course.is_active = bool(is_active)
        if not course.is_active:
            now = datetime.now(timezone.utc)
            open_sessions = db.session.scalars(
                select(AttendanceSession).where(
                    AttendanceSession.course_id == course.id,
                    AttendanceSession.closed_at.is_(None),
                )
            ).all()
            student_ids = {
                enrollment.student_id for enrollment in course.enrollments
            }
            for attendance_session in open_sessions:
                existing_ids = set(
                    db.session.scalars(
                        select(Attendance.student_id).where(
                            Attendance.session_id == attendance_session.id
                        )
                    ).all()
                )
                for student_id in student_ids - existing_ids:
                    db.session.add(
                        Attendance(
                            session_id=attendance_session.id,
                            student_id=student_id,
                            recorded_at=now,
                            status="ausente",
                            source="cierre",
                        )
                    )
                attendance_session.active = False
                attendance_session.closed_at = now
        if previous_active != course.is_active:
            AuditService.record(
                actor_id, "course_availability_changed", "course", course.id,
                {"is_active": course.is_active},
            )
        db.session.commit()
        return course

    @staticmethod
    def _students_from_ids(student_ids):
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
