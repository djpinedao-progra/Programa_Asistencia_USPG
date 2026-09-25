import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Attendance, AttendanceSession, Course, User
from app.repositories import AttendanceRepository, CourseRepository, UserRepository


class UserService:
    ALLOWED_ROLES = {"admin", "docente", "alumno"}

    def __init__(self, users=None):
        self.users = users or UserRepository()

    def create_user(self, name, email, password, role, carnet=""):
        name, email = name.strip(), email.strip().lower()
        carnet = carnet.strip()
        if not name or "@" not in email or not password:
            raise ValueError("Completa todos los datos y elige una contraseña.")
        if role not in self.ALLOWED_ROLES:
            raise ValueError("El rol seleccionado no es válido.")
        if role == "alumno" and not re.fullmatch(r"\d{7}", carnet):
            raise ValueError("El carnet debe tener exactamente 7 dígitos, por ejemplo 2600403.")
        if self.users.find_by_email(email):
            raise ValueError("Ya existe una cuenta con ese correo.")
        if carnet and self.users.find_by_carnet(carnet):
            raise ValueError("Ya existe una cuenta con ese carnet.")
        user = User(name=name, email=email, carnet=carnet or None, role=role)
        user.set_password(password)
        try:
            return self.users.add(user)
        except IntegrityError as error:
            db.session.rollback()
            raise ValueError("Ya existe una cuenta con ese correo o carnet.") from error

    def register_student(self, name, email, carnet, password):
        return self.create_user(name, email, password, "alumno", carnet)

    def assign_student_carnet(self, user_id, carnet):
        carnet = carnet.strip()
        if not re.fullmatch(r"\d{7}", carnet):
            raise ValueError("El carnet debe tener exactamente 7 dígitos.")
        user = self.users.find_by_id(user_id)
        if not user or user.role != "alumno":
            raise ValueError("Solo se puede asignar carnet a una cuenta de alumno.")
        existing_user = self.users.find_by_carnet(carnet)
        if existing_user and existing_user.id != user.id:
            raise ValueError("Ese carnet ya pertenece a otra cuenta.")
        user.carnet = carnet
        try:
            return self.users.save(user)
        except IntegrityError as error:
            db.session.rollback()
            raise ValueError("Ese carnet ya pertenece a otra cuenta.") from error


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


class AttendanceService:
    def __init__(self, attendance=None, courses=None, session_minutes=15):
        self.attendance = attendance or AttendanceRepository()
        self.courses = courses or CourseRepository()
        self.session_minutes = session_minutes

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
            db.session.rollback()
            raise ValueError("Tu asistencia ya quedó registrada.") from error
        return attendance