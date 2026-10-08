import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (
    Attendance,
    AttendanceSession,
    AuditLog,
    Course,
    CourseEnrollment,
    PasswordReplacement,
    User,
)
from app.repositories import AttendanceRepository, CourseRepository, UserRepository


class AuditService:
    @staticmethod
    def record(actor_id, action, entity_type, entity_id=None, details=None):
        db.session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details or {},
            )
        )


class UserService:
    ALLOWED_ROLES = {"admin", "docente", "alumno"}
    EMAIL_ROLES = {
        "administrador.uspg.edu.gt": "admin",
        "catedratico.uspg.edu.gt": "docente",
        "alumno.uspg.edu.gt": "alumno",
    }
    ROLE_DOMAINS = {role: domain for domain, role in EMAIL_ROLES.items()}

    @classmethod
    def email_role(cls, email):
        email = (email or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+", email):
            return None
        return cls.EMAIL_ROLES.get(email.split("@")[1])

    @classmethod
    def validate_email_role(cls, email, role):
        if cls.email_role(email) != role:
            domain = cls.ROLE_DOMAINS.get(role)
            raise ValueError(
                f"Para este rol usa un correo institucional @{domain}."
                if domain else "El correo no corresponde al rol seleccionado."
            )

    def __init__(self, users=None):
        self.users = users or UserRepository()

    def create_user(self, name, email, password, role, carnet="", actor_id=None):
        name, email = name.strip(), email.strip().lower()
        carnet = carnet.strip()
        if not name or "@" not in email or not password:
            raise ValueError("Completa todos los datos y elige una contraseña.")
        if role not in self.ALLOWED_ROLES:
            raise ValueError("El rol seleccionado no es válido.")
        self.validate_email_role(email, role)
        if role == "alumno" and not re.fullmatch(r"\d{7}", carnet):
            raise ValueError("El carnet debe tener exactamente 7 dígitos, por ejemplo 2600403.")
        if self.users.find_by_email(email):
            raise ValueError("Ya existe una cuenta con ese correo.")
        if carnet and self.users.find_by_carnet(carnet):
            raise ValueError("Ya existe una cuenta con ese carnet.")
        user = User(name=name, email=email, carnet=carnet or None, role=role)
        user.set_password(password)
        try:
            db.session.add(user)
            db.session.flush()
            AuditService.record(
                actor_id or user.id, "user_created", "user", user.id,
                {"role": role},
            )
            return self.users.add(user)
        except IntegrityError as error:
            db.session.rollback()
            raise ValueError("Ya existe una cuenta con ese correo o carnet.") from error

    def register_student(self, name, email, carnet, password):
        return self.create_user(name, email, password, "alumno", carnet)

    def assign_student_carnet(self, user_id, carnet, actor_id=None):
        carnet = carnet.strip()
        if not re.fullmatch(r"\d{7}", carnet):
            raise ValueError("El carnet debe tener exactamente 7 dígitos.")
        user = self.users.find_by_id(user_id)
        if not user or user.role != "alumno":
            raise ValueError("Solo se puede asignar carnet a una cuenta de alumno.")
        existing_user = self.users.find_by_carnet(carnet)
        if existing_user and existing_user.id != user.id:
            raise ValueError("Ese carnet ya pertenece a otra cuenta.")
        previous_carnet = user.carnet
        user.carnet = carnet
        if previous_carnet != carnet:
            AuditService.record(
                actor_id, "carnet_updated", "user", user.id,
                {"previous_carnet": previous_carnet, "carnet": carnet},
            )
        try:
            return self.users.save(user)
        except IntegrityError as error:
            db.session.rollback()
            raise ValueError("Ese carnet ya pertenece a otra cuenta.") from error

    def update_profile(self, user_id, name, email, carnet="", actor_id=None):
        user = self.users.find_by_id(user_id)
        name, email, carnet = name.strip(), email.strip().lower(), carnet.strip()
        if not user or user.role not in {"alumno", "docente"}:
            raise ValueError("No se encontró el perfil académico.")
        if not name or "@" not in email:
            raise ValueError("Indica un nombre y correo institucional válidos.")
        self.validate_email_role(email, user.role)
        existing_email = self.users.find_by_email(email)
        if existing_email and existing_email.id != user.id:
            raise ValueError("Ese correo ya pertenece a otra cuenta.")
        if user.role == "alumno" and carnet and not re.fullmatch(r"\d{7}", carnet):
            raise ValueError("El carnet debe contener exactamente 7 dígitos.")
        if user.role == "alumno" and carnet:
            existing_carnet = self.users.find_by_carnet(carnet)
            if existing_carnet and existing_carnet.id != user.id:
                raise ValueError("Ese carnet ya pertenece a otra cuenta.")
        changed_fields = [
            field for field, old, new in (
                ("name", user.name, name),
                ("email", user.email, email),
                ("carnet", user.carnet, carnet or None),
            ) if old != new and (field != "carnet" or user.role == "alumno")
        ]
        user.name = name
        user.email = email
        if user.role == "alumno":
            user.carnet = carnet or None
        if changed_fields:
            AuditService.record(
                actor_id, "profile_updated", "user", user.id,
                {"changed_fields": changed_fields},
            )
        try:
            return self.users.save(user)
        except IntegrityError as error:
            db.session.rollback()
            raise ValueError("El correo o carnet ya pertenece a otra cuenta.") from error

    def change_password(self, user_id, current_password, new_password, confirmation):
        user = self.users.find_by_id(user_id)
        if not user or not user.check_password(current_password):
            raise ValueError("La contraseña actual no es correcta.")
        self._save_new_password(
            user, new_password, confirmation, user.id, "password_changed"
        )

    def admin_reset_password(self, user_id, new_password, confirmation, actor_id=None):
        user = self.users.find_by_id(user_id)
        if not user or user.role not in {"alumno", "docente"}:
            raise ValueError("No se encontró la cuenta académica.")
        self._save_new_password(
            user, new_password, confirmation, actor_id, "password_reset"
        )

    @staticmethod
    def _save_new_password(user, new_password, confirmation, actor_id, action):
        if not new_password:
            raise ValueError("La nueva contraseña no puede estar vacía.")
        if new_password != confirmation:
            raise ValueError("La confirmación de contraseña no coincide.")
        user.set_password(new_password)
        pending = db.session.get(PasswordReplacement, user.id)
        if pending:
            db.session.delete(pending)
        AuditService.record(actor_id, action, "user", user.id)
        db.session.commit()


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
        if not db.session.scalar(
            select(CourseEnrollment.id).where(
                CourseEnrollment.course_id == attendance_session.course_id,
                CourseEnrollment.student_id == student.id,
            )
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
            db.session.rollback()
            raise ValueError("Tu asistencia ya quedó registrada.") from error
        return attendance