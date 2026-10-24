import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.models import Attendance, Course, CourseEnrollment
from app.repositories import AttendanceRepository, CourseRepository, UserRepository
from app.services.audit_service import AuditService
from app.services.course_enrollment_service import CourseEnrollmentService

CLASSROOMS = tuple(f"Salón {number}" for number in range(1, 26))
WEEKDAYS = (
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
)


def _normalized(value):
    return "".join(
        character for character in unicodedata.normalize("NFD", value.casefold())
        if unicodedata.category(character) != "Mn"
    )


def parse_schedule(schedule):
    normalized_schedule = _normalized(schedule or "")
    days = {
        day for day in WEEKDAYS if _normalized(day) in normalized_schedule
    }
    time_match = re.search(
        r"\b([01]?\d|2[0-3]):([0-5]\d)\s*[-–—]\s*"
        r"([01]?\d|2[0-3]):([0-5]\d)\b",
        schedule or "",
    )
    if not days or not time_match:
        return None
    start = int(time_match.group(1)) * 60 + int(time_match.group(2))
    end = int(time_match.group(3)) * 60 + int(time_match.group(4))
    if start >= end:
        return None
    return {
        "days": days,
        "start": start,
        "end": end,
        "start_time": f"{int(time_match.group(1)):02d}:{time_match.group(2)}",
        "end_time": f"{int(time_match.group(3)):02d}:{time_match.group(4)}",
    }


def build_schedule(days, start_time, end_time):
    selected_days = [day for day in WEEKDAYS if day in set(days)]
    candidate = f"{' y '.join(selected_days)}, {start_time}–{end_time}"
    parsed = parse_schedule(candidate)
    if not parsed:
        raise ValueError(
            "Selecciona al menos un día y un horario de inicio y fin válido."
        )
    return candidate


class CourseService:
    def __init__(self, courses=None, users=None, attendance=None):
        self.courses = courses or CourseRepository()
        self.users = users or UserRepository()
        self.attendance = attendance or AttendanceRepository()

    def list_all(self):
        return self.courses.list_all()

    def list_for_teacher(self, teacher_id):
        return self.courses.list_for_teacher(teacher_id)

    def get_by_id(self, course_id):
        return self.courses.get_by_id(course_id)

    def get_for_teacher(self, course_id, teacher_id):
        return self.courses.get_for_teacher(course_id, teacher_id)

    def create_course(self, name, code, teacher_id):
        name, code = name.strip(), code.strip().upper()
        if not name or not code:
            raise ValueError("El nombre y el código del curso son obligatorios.")
        course = Course(name=name, code=code, teacher_id=teacher_id)
        try:
            return self.courses.add(course)
        except IntegrityError as error:
            self.courses.rollback()
            raise ValueError("Ese código de curso ya está registrado.") from error

    def create_course_for_admin(
        self, name, code, teacher_id, schedule, location_type, classroom,
        student_ids, actor_id=None,
    ):
        name, code = name.strip(), code.strip().upper()
        schedule, classroom = schedule.strip(), classroom.strip()
        if not name or not code or not schedule:
            raise ValueError("Completa el nombre, código y horario del curso.")
        teacher = self.users.find_by_id(teacher_id)
        if not teacher or teacher.role != "docente":
            raise ValueError("Selecciona un docente válido para el curso.")
        if location_type not in {"presencial", "virtual"}:
            raise ValueError("Selecciona una modalidad válida.")
        self._validate_schedule_and_classroom(
            schedule, location_type, classroom, teacher.id
        )
        if location_type == "virtual":
            classroom = "Virtual"
        students = CourseEnrollmentService().students_from_ids(student_ids)
        if self.courses.find_by_code(code):
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
            self.courses.stage(course)
            AuditService.record(
                actor_id, "course_created", "course", course.id,
                {
                    "code": course.code,
                    "teacher_id": teacher.id,
                    "student_ids": sorted(student.id for student in students),
                },
            )
            self.courses.commit()
            return course
        except IntegrityError as error:
            self.courses.rollback()
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
        course = self.courses.get_by_id(course_id)
        if not course:
            raise ValueError("No se encontró el curso.")
        teacher = self.users.find_by_id(teacher_id)
        if not teacher or teacher.role != "docente":
            raise ValueError("Selecciona un docente válido para el curso.")
        schedule, classroom = schedule.strip(), classroom.strip()
        if not schedule:
            raise ValueError("El horario del curso es obligatorio.")
        if location_type not in {"presencial", "virtual"}:
            raise ValueError("Selecciona una modalidad válida.")
        self._validate_schedule_and_classroom(
            schedule, location_type, classroom, teacher.id, course.id,
            course_is_active=bool(is_active),
        )
        students = CourseEnrollmentService().students_from_ids(student_ids)
        name = (name if name is not None else course.name).strip()
        code = (code if code is not None else course.code).strip().upper()
        if not name or not code:
            raise ValueError("El nombre y el código del curso son obligatorios.")
        duplicate_code = self.courses.find_by_code_except(code, course.id)
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
                self.courses.delete_enrollment(enrollment)
        for student in students:
            if student.id not in existing_ids:
                course.enrollments.append(CourseEnrollment(student=student))
        try:
            course_sessions = self.attendance.list_sessions_for_course(course.id)
            closed_sessions = []
            for attendance_session in course_sessions:
                if not course.is_active and attendance_session.closed_at is None:
                    attendance_session.active = False
                    attendance_session.closed_at = datetime.now(timezone.utc)
                if attendance_session.closed_at is not None:
                    closed_sessions.append(attendance_session)
            existing_attendance = (
                self.attendance.list_attendance_pairs_for_course(course.id)
            )
            absences = []
            for student in students:
                for attendance_session in closed_sessions:
                    if (student.id, attendance_session.id) not in existing_attendance:
                        absences.append(
                            Attendance(
                                session_id=attendance_session.id,
                                student_id=student.id,
                                recorded_at=attendance_session.closed_at,
                                status="ausente",
                                source="cierre",
                            )
                        )
            self.attendance.add_many(absences)
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
            self.courses.commit()
        except IntegrityError as error:
            self.courses.rollback()
            raise ValueError("No se pudieron actualizar las asignaciones.") from error
        return course

    def _validate_schedule_and_classroom(
        self, schedule, location_type, classroom, teacher_id,
        excluded_course_id=None,
        course_is_active=True,
    ):
        requested = parse_schedule(schedule)
        if not requested:
            raise ValueError(
                "Selecciona al menos un día y un horario de inicio y fin válido."
            )
        if location_type == "presencial" and classroom not in CLASSROOMS:
            raise ValueError("Selecciona uno de los 25 salones disponibles.")
        if not course_is_active:
            return
        for existing in self.courses.list_all():
            if (
                existing.id == excluded_course_id
                or not existing.is_active
            ):
                continue
            occupied = parse_schedule(existing.schedule)
            if not occupied or requested["days"].isdisjoint(occupied["days"]):
                continue
            if (
                requested["start"] < occupied["end"]
                and occupied["start"] < requested["end"]
            ):
                conflicting_days = ", ".join(
                    day for day in WEEKDAYS
                    if day in requested["days"] & occupied["days"]
                )
                if (
                    location_type == "presencial"
                    and existing.location_type == "presencial"
                    and existing.classroom == classroom
                ):
                    raise ValueError(
                        f"{classroom} ya está ocupado el {conflicting_days} "
                        f"de {occupied['start_time']} a {occupied['end_time']} "
                        f"por {existing.code}."
                    )
                if existing.teacher_id == teacher_id:
                    raise ValueError(
                        f"El docente ya imparte {existing.code} el {conflicting_days} "
                        f"de {occupied['start_time']} a {occupied['end_time']}."
                    )

    def bulk_enroll(self, enrollments, actor_id=None):
        return CourseEnrollmentService().bulk_enroll(enrollments, actor_id)

    def set_course_active(self, course_id, is_active, actor_id=None):
        course = self.courses.get_by_id(course_id)
        if not course:
            raise ValueError("No se encontró el curso.")
        previous_active = course.is_active
        course.is_active = bool(is_active)
        if not course.is_active:
            now = datetime.now(timezone.utc)
            open_sessions = self.attendance.list_sessions_for_course(
                course.id, open_only=True
            )
            absences = []
            student_ids = {
                enrollment.student_id for enrollment in course.enrollments
            }
            for attendance_session in open_sessions:
                existing_ids = set(
                    self.attendance.list_student_ids_for_session(
                        attendance_session.id
                    )
                )
                for student_id in student_ids - existing_ids:
                    absences.append(
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
            self.attendance.add_many(absences)
        if previous_active != course.is_active:
            AuditService.record(
                actor_id, "course_availability_changed", "course", course.id,
                {"is_active": course.is_active},
            )
        self.courses.commit()
        return course
