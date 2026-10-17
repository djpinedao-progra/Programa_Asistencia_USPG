"""Creación idempotente de los datos de demostración."""
from app.models import Course, CourseEnrollment, User
from app.repositories import CourseRepository, UserRepository


DEMO_USERS = (
    ("Administrador Demo", "admin@administrador.uspg.edu.gt", "admin", None),
    ("Docente Demo", "docente@catedratico.uspg.edu.gt", "docente", None),
    ("Estudiante Demo", "alumno@alumno.uspg.edu.gt", "alumno", "2600001"),
)
DEMO_PASSWORD = "Demo-USPG-2026!"


def seed_demo_data():
    """Crea las cuentas, curso y matrícula demo si aún no existen."""
    users = UserRepository()
    missing_users = []
    for name, email, role, carnet in DEMO_USERS:
        if not users.find_by_email(email):
            user = User(name=name, email=email, role=role, carnet=carnet)
            user.set_password(DEMO_PASSWORD)
            missing_users.append(user)
    if missing_users:
        users.add_many(missing_users)

    teacher = users.find_by_email("docente@catedratico.uspg.edu.gt")
    student = users.find_by_email("alumno@alumno.uspg.edu.gt")
    courses = CourseRepository()
    if not courses.find_by_code("DEMO-101"):
        course = Course(
            name="Programación II",
            code="DEMO-101",
            teacher_id=teacher.id,
            schedule="Sábado 08:00–10:00",
            classroom="Laboratorio 1",
        )
        course.enrollments = [CourseEnrollment(student=student)]
        courses.add(course)
