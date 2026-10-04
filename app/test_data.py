import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update

from app import db
from app.models import (
    Attendance,
    AttendanceSession,
    AuditLog,
    Course,
    CourseEnrollment,
    Notice,
    User,
)

TEST_PASSWORD = "123"

TEST_USERS = [
    ("Administrador Demo", "admin@uspg.edu", "admin", None),
    ("Carlos Méndez", "docente@uspg.edu", "docente", None),
    ("Ana López", "alumno1@uspg.edu", "alumno", "2600010"),
    ("Luis Pérez", "alumno2@uspg.edu", "alumno", "2600011"),
    ("María García", "alumno3@uspg.edu", "alumno", "2600012"),
    ("Carlos Morales", "alumno4@uspg.edu", "alumno", "2600013"),
    ("José Hernández", "alumno5@uspg.edu", "alumno", "2600014"),
    ("Sofía Castillo", "alumno6@uspg.edu", "alumno", "2600015"),
]

TEST_COURSES = [
    ("Programación de Sistemas II", "ING-220", "Lunes y miércoles, 10:00–12:00", "presencial", "Aula 204"),
    ("Base de Datos", "ING-221", "Martes y jueves, 08:00–10:00", "presencial", "Laboratorio 2"),
    ("Ingeniería de Software", "ING-222", "Viernes, 14:00–17:00", "virtual", "Plataforma virtual"),
]

SESSIONS_PER_COURSE = 10
# Session numbers each student misses in every course; gives 100, 90, 80, 63, 70 and 90 percent.
ABSENT_SESSIONS = {
    "alumno1@uspg.edu": set(),
    "alumno2@uspg.edu": {2},
    "alumno3@uspg.edu": {1, 4},
    "alumno4@uspg.edu": {0, 3, 6},
    "alumno5@uspg.edu": {1, 5},
    "alumno6@uspg.edu": {7},
}
EXTRA_ABSENCES = {("ING-222", "alumno4@uspg.edu"): {8, 9}}
JUSTIFIED_SESSIONS = {"alumno5@uspg.edu": {9}}

# Account created by the first version of seed-test-users; removed so teams don't keep it.
LEGACY_TEST_STUDENT = ("alumno@uspg.edu", "Alumno de prueba", "2600001")


def _remove_legacy_test_student():
    email, name, carnet = LEGACY_TEST_STUDENT
    legacy = db.session.scalar(
        select(User).where(User.email == email, User.name == name, User.carnet == carnet)
    )
    if legacy is None:
        return None
    for model in (Attendance, CourseEnrollment, Notice):
        db.session.execute(delete(model).where(model.student_id == legacy.id))
    db.session.execute(update(AuditLog).where(AuditLog.actor_id == legacy.id).values(actor_id=None))
    db.session.delete(legacy)
    db.session.flush()
    return f"{email}: cuenta de prueba anterior eliminada"


def seed_test_data():
    """Create or reset the shared test accounts, courses and attendance history."""
    messages = []
    removed = _remove_legacy_test_student()
    if removed:
        messages.append(removed)
    users = {}
    for name, email, role, carnet in TEST_USERS:
        user = db.session.scalar(select(User).where(User.email == email))
        if user is None:
            if carnet and db.session.scalar(select(User).where(User.carnet == carnet)):
                carnet = None
            user = User(name=name, email=email, role=role, carnet=carnet)
            db.session.add(user)
            action = "creada"
        elif user.role != role:
            db.session.rollback()
            raise ValueError(
                f"{email} ya existe con el rol {user.role}; no se modificó ninguna cuenta."
            )
        else:
            user.name = name
            if carnet and not user.carnet and not db.session.scalar(
                select(User).where(User.carnet == carnet)
            ):
                user.carnet = carnet
            action = "actualizada"
        user.set_password(TEST_PASSWORD)
        users[email] = user
        messages.append(f"{email} ({role}): {action}")
    db.session.flush()

    teacher = users["docente@uspg.edu"]
    students = [users[email] for _, email, role, _ in TEST_USERS if role == "alumno"]
    now = datetime.now(timezone.utc)
    for index, (name, code, schedule, location_type, classroom) in enumerate(TEST_COURSES):
        if db.session.scalar(select(Course).where(Course.code == code)):
            messages.append(f"Curso {code}: ya existe, no se modificó")
            continue
        course = Course(
            name=name,
            code=code,
            teacher_id=teacher.id,
            schedule=schedule,
            location_type=location_type,
            classroom=classroom,
        )
        db.session.add(course)
        db.session.flush()
        for student in students:
            db.session.add(CourseEnrollment(course_id=course.id, student_id=student.id))
        for number in range(SESSIONS_PER_COURSE):
            created = now - timedelta(days=(SESSIONS_PER_COURSE - number) * 3 + index, hours=2)
            attendance_session = AttendanceSession(
                course_id=course.id,
                token_hash=secrets.token_hex(32),
                created_at=created,
                expires_at=created + timedelta(minutes=5),
                active=False,
                closed_at=created + timedelta(hours=1),
            )
            db.session.add(attendance_session)
            db.session.flush()
            for offset, student in enumerate(students):
                missed = number in ABSENT_SESSIONS[student.email] | EXTRA_ABSENCES.get(
                    (code, student.email), set()
                )
                if missed:
                    status, source = "ausente", "cierre"
                elif number in JUSTIFIED_SESSIONS.get(student.email, set()):
                    status, source = "justificado", "manual"
                else:
                    status, source = "presente", "qr"
                db.session.add(
                    Attendance(
                        session_id=attendance_session.id,
                        student_id=student.id,
                        recorded_at=created + timedelta(minutes=3 + offset),
                        status=status,
                        source=source,
                    )
                )
        messages.append(f"Curso {code}: creado con {SESSIONS_PER_COURSE} sesiones de asistencia")
    db.session.commit()
    return messages
