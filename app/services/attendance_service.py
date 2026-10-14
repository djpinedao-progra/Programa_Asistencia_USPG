import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.models import Attendance, AttendanceSession
from app.repositories import AttendanceRepository, CourseRepository


class AttendanceService:
    def __init__(self, attendance=None, courses=None, session_minutes=1):
        self.attendance = attendance or AttendanceRepository()
        self.courses = courses or CourseRepository()
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
