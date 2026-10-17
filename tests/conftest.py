from datetime import datetime, timedelta, timezone
import secrets

import pytest
from flask import g

from app import create_app, db
from app.models import (
    Attendance,
    AttendanceSession,
    Course,
    CourseEnrollment,
    User,
)


@pytest.fixture
def app():
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "x",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def sample_data(app):
    with app.app_context():
        admin = User(name="Admin", email="admin@administrador.uspg.edu.gt", role="admin")
        teacher = User(
            name="Docente",
            email="docente@catedratico.uspg.edu.gt",
            role="docente",
        )
        student = User(
            name="Alumno",
            email="alumno@alumno.uspg.edu.gt",
            carnet="2600001",
            role="alumno",
        )
        other_student = User(
            name="Otra alumna",
            email="otra@alumno.uspg.edu.gt",
            carnet="2600002",
            role="alumno",
        )
        outsider = User(
            name="Alumno no matriculado",
            email="externo@alumno.uspg.edu.gt",
            carnet="2600003",
            role="alumno",
        )
        for user in (admin, teacher, student, other_student, outsider):
            user.set_password("Password123!")
        db.session.add_all((admin, teacher, student, other_student, outsider))
        db.session.flush()

        course = Course(
            name="Programación",
            code="PROG-1",
            teacher_id=teacher.id,
            schedule="Lunes, 08:00–10:00",
            location_type="presencial",
            classroom="Salón 1",
        )
        db.session.add(course)
        db.session.flush()
        db.session.add(CourseEnrollment(course_id=course.id, student_id=student.id))

        now = datetime.now(timezone.utc)
        closed_session = AttendanceSession(
            course_id=course.id,
            token_hash="a" * 64,
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
            active=False,
            closed_at=now - timedelta(hours=1),
        )
        db.session.add(closed_session)
        db.session.flush()
        db.session.add(
            Attendance(
                session_id=closed_session.id,
                student_id=student.id,
                recorded_at=now - timedelta(hours=1),
                status="presente",
                source="qr",
            )
        )
        db.session.commit()
        return {
            "admin_id": admin.id,
            "teacher_id": teacher.id,
            "student_id": student.id,
            "other_student_id": other_student.id,
            "outsider_id": outsider.id,
            "course_id": course.id,
            "closed_session_id": closed_session.id,
        }


@pytest.fixture
def login_as(app):
    def authenticate(client, user_id):
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        g.pop("_login_user", None)

    return authenticate


@pytest.fixture
def csrf_token():
    def token_for(client):
        client.get("/")
        with client.session_transaction() as session:
            if "csrf_token" not in session:
                session["csrf_token"] = secrets.token_urlsafe(32)
            return session["csrf_token"]

    return token_for
