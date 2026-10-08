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

ADMIN_EMAIL = "admin@administrador.uspg.edu.gt"
TEACHER_EMAIL = "docente@catedratico.uspg.edu.gt"


def student_email(number):
    return f"alumno{number}@alumno.uspg.edu.gt"


TEST_USERS = [
    ("Administrador Demo", ADMIN_EMAIL, "admin", None),
    ("Carlos Méndez", TEACHER_EMAIL, "docente", None),
    ("Ana López", student_email(1), "alumno", "2600010"),
    ("Luis Pérez", student_email(2), "alumno", "2600011"),
    ("María García", student_email(3), "alumno", "2600012"),
    ("Carlos Morales", student_email(4), "alumno", "2600013"),
    ("José Hernández", student_email(5), "alumno", "2600014"),
    ("Sofía Castillo", student_email(6), "alumno", "2600015"),
]

# Earlier versions used @uspg.edu; those accounts are renamed so their data is kept.
LEGACY_EMAILS = {
    "admin@uspg.edu": ADMIN_EMAIL,
    "docente@uspg.edu": TEACHER_EMAIL,
    **{f"alumno{number}@uspg.edu": student_email(number) for number in range(1, 7)},
}

TEST_COURSES = [
    ("Programación de Sistemas II", "ING-220", "Lunes y miércoles, 10:00–12:00", "presencial", "Aula 204"),
    ("Base de Datos", "ING-221", "Martes y jueves, 08:00–10:00", "presencial", "Laboratorio 2"),
    ("Ingeniería de Software", "ING-222", "Viernes, 14:00–17:00", "virtual", "Plataforma virtual"),
]

SESSIONS_PER_COURSE = 10
# Session numbers each student misses in every course; gives 100, 90, 80, 63, 70 and 90 percent.
ABSENT_SESSIONS = {
    student_email(1): set(),
    student_email(2): {2},
    student_email(3): {1, 4},
    student_email(4): {0, 3, 6},
    student_email(5): {1, 5},
    student_email(6): {7},
}
EXTRA_ABSENCES = {("ING-222", student_email(4)): {8, 9}}
JUSTIFIED_SESSIONS = {student_email(5): {9}}

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


def _rename_legacy_emails():
    messages = []
    for old_email, new_email in LEGACY_EMAILS.items():
        user = db.session.scalar(select(User).where(User.email == old_email))
        if user and not db.session.scalar(select(User).where(User.email == new_email)):
            user.email = new_email
            messages.append(f"{old_email}: renombrada a {new_email}")
    db.session.flush()
    return messages


def seed_test_data():
    """Create or reset the shared test accounts, courses and attendance history."""
    messages = []
    removed = _remove_legacy_test_student()
    if removed:
        messages.append(removed)
    messages.extend(_rename_legacy_emails())
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

    teacher = users[TEACHER_EMAIL]
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
