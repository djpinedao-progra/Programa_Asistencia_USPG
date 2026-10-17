import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.models import Attendance, AttendanceSession
from app.repositories import (
    AttendanceMetricsRepository,
    AttendanceRepository,
    CourseRepository,
    UserRepository,
)
from app.services.audit_service import AuditService
from app.services.metrics_service import course_roster
from app.utils.time_utils import local_date_bounds_or_none


class AttendanceService:
    def __init__(
        self, attendance=None, courses=None, users=None, session_minutes=1
    ):
        self.attendance = attendance or AttendanceRepository()
        self.metrics = AttendanceMetricsRepository()
        self.courses = courses or CourseRepository()
        self.users = users or UserRepository()
        self.session_minutes = min(session_minutes, 1)

    def create_session(self, course_id, teacher_id):
        course = self.courses.get_for_teacher(course_id, teacher_id)
        if not course:
            raise ValueError("No tienes permiso para abrir asistencia en ese curso.")
        raw_token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        attendance_session = AttendanceSession(
            course_id=course.id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            created_at=now,
            expires_at=now + timedelta(minutes=self.session_minutes),
            active=True,
        )
        self.attendance.add_session(attendance_session)
        return attendance_session, raw_token

    def find_session_by_id(self, session_id):
        return self.attendance.find_session_by_id(session_id)

    def find_open_session_for_course(self, course_id):
        return self.attendance.find_open_session_for_course(course_id)

    def list_for_session(self, session_id):
        return self.attendance.list_for_session(session_id)

    def list_for_course(self, course_id):
        return self.attendance.list_for_course(course_id)

    def teacher_history_data(self, course_ids, filters, page, timezone_name):
        selected_course_id = None
        if filters["curso"]:
            if filters["curso"].isdigit() and int(filters["curso"]) in course_ids:
                selected_course_id = int(filters["curso"])
            else:
                selected_course_id = -1
        bounds = (
            local_date_bounds_or_none(filters["fecha"], timezone_name)
            if filters["fecha"]
            else None
        )
        return self.list_teacher_history(
            course_ids,
            selected_course_id,
            bounds,
            bool(filters["fecha"] and bounds is None),
            filters["estudiante"],
            filters["estado"],
            page,
        )

    def list_teacher_history(
        self,
        course_ids,
        selected_course_id,
        date_bounds,
        invalid_date,
        student_search,
        status,
        page,
    ):
        return self.metrics.list_teacher_history(
            course_ids,
            selected_course_id,
            date_bounds,
            invalid_date,
            student_search,
            status,
            page,
        )

    def record_attendance(self, raw_token, student):
        if student.role != "alumno":
            raise ValueError("Solo los alumnos pueden registrar asistencia.")
        if not raw_token:
            raise ValueError("El código QR no contiene un token válido.")
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        attendance_session = self.attendance.find_session_by_token_hash(token_hash)
        if not attendance_session or not attendance_session.active:
            raise ValueError("La sesión de asistencia no está activa.")
        if not self.attendance.is_student_enrolled(
            attendance_session.course_id, student.id
        ):
            raise ValueError("No estás asignado a este curso.")
        expiration = attendance_session.expires_at
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        if expiration <= datetime.now(timezone.utc):
            raise ValueError("El código QR ya venció. Pide uno nuevo al docente.")
        attendance = Attendance(
            session_id=attendance_session.id,
            student_id=student.id,
            recorded_at=datetime.now(timezone.utc),
        )
        try:
            self.attendance.record(attendance)
        except IntegrityError as error:
            raise ValueError("Tu asistencia ya quedó registrada.") from error
        return attendance

    def renew_token(self, attendance_session):
        raw_token = secrets.token_urlsafe(32)
        attendance_session.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        attendance_session.expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self.session_minutes
        )
        attendance_session.active = True
        attendance_session.closed_at = None
        self.attendance.save_session(attendance_session)
        return raw_token

    def close_session(self, attendance_session, actor_id):
        now = datetime.now(timezone.utc)
        existing_ids = set(
            self.attendance.list_student_ids_for_session(attendance_session.id)
        )
        absences = [
            Attendance(
                session_id=attendance_session.id,
                student_id=student.id,
                recorded_at=now,
                status="ausente",
                source="cierre",
                modified_by_id=actor_id,
            )
            for student in course_roster(attendance_session.course_id)
            if student.id not in existing_ids
        ]
        attendance_session.active = False
        attendance_session.closed_at = now
        self.attendance.save_session_with_attendances(
            attendance_session, absences
        )

    def correct_attendance_record(self, attendance_id, teacher_id, status):
        attendance = self.attendance.find_attendance_by_id(attendance_id)
        if (
            not attendance
            or attendance.session.course.teacher_id != teacher_id
        ):
            return False
        if status not in {"presente", "ausente", "justificado"}:
            raise ValueError("Estado de asistencia inválido.")
        previous_status = attendance.status
        attendance.status = status
        attendance.source = "manual"
        attendance.modified_by_id = teacher_id
        attendance.modified_at = datetime.now(timezone.utc)
        AuditService.record(
            teacher_id,
            "attendance_corrected",
            "attendance",
            attendance.id,
            {
                "student_id": attendance.student_id,
                "session_id": attendance.session_id,
                "previous_status": previous_status,
                "status": status,
            },
        )
        self.attendance.commit_changes()
        return True

    def set_manual_attendance(self, session_id, student_id, teacher_id, status):
        attendance_session = self.attendance.find_session_by_id(session_id)
        if (
            not attendance_session
            or attendance_session.course.teacher_id != teacher_id
        ):
            return None
        if not self.is_course_student(attendance_session.course_id, student_id):
            return None
        student = self.users.find_by_id(student_id)
        attendance = self.attendance.find_for_session_and_student(
            session_id, student_id
        )
        now = datetime.now(timezone.utc)
        previous_status = attendance.status if attendance else None
        if attendance is None:
            attendance = Attendance(
                session_id=session_id,
                student_id=student_id,
                recorded_at=now,
            )
            self.attendance.stage_attendance(attendance)
        else:
            attendance.modified_at = now
        attendance.status = status
        attendance.source = "manual"
        attendance.modified_by_id = teacher_id
        AuditService.record(
            teacher_id,
            "attendance_corrected",
            "attendance",
            attendance.id,
            {
                "student_id": student.id,
                "session_id": session_id,
                "previous_status": previous_status,
                "status": status,
            },
        )
        self.attendance.commit_changes()
        return attendance

    def is_course_student(self, course_id, student_id):
        student = self.users.find_by_id(student_id)
        return bool(student and student in course_roster(course_id))
