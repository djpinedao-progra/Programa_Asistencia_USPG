import re
from datetime import datetime, timezone

from sqlalchemy import select

from app import db
from app.models import Attendance, AttendanceSession, Course, User


def create_user(name, email, role, carnet=None):
    user = User(name=name, email=email, role=role, carnet=carnet)
    user.set_password("password-seguro-123")
    db.session.add(user)
    db.session.commit()
    return user


def login(client, identifier, password="password-seguro-123"):
    with client.session_transaction() as client_session:
        client_session.clear()
    page = client.get("/")
    assert page.status_code == 200, (page.status_code, page.location, page.data[:300])
    csrf_token = re.search(
        rb'name="csrf_token" value="([^"]+)"', page.data
    ).group(1).decode()
    response = client.post(
        "/",
        data={
            "csrf_token": csrf_token,
            "identifier": identifier,
            "password": password,
        },
    )
    assert response.status_code == 302


def test_teacher_qr_flow_records_student_attendance(app):
    with app.app_context():
        teacher = create_user("Docente", "docente@uspg.edu", "docente")
        student = create_user("Alumno", "alumno@uspg.edu", "alumno", "2600403")
        course = Course(name="Programación", code="INF-101", teacher_id=teacher.id)
        db.session.add(course)
        db.session.commit()
        student_id = student.id

    teacher_client = app.test_client()
    login(teacher_client, "docente@uspg.edu")
    response = teacher_client.post(
        "/docente/cursos/1/sesion",
        data={
            "csrf_token": re.search(
                rb'name="csrf_token" value="([^"]+)"',
                teacher_client.get("/docente").data,
            ).group(1).decode()
        },
    )
    assert response.status_code == 302
    qr_page = teacher_client.get(response.location)
    assert qr_page.status_code == 200
    assert b"data:image/png;base64," in qr_page.data
    with teacher_client.session_transaction() as teacher_session:
        token = next(iter(teacher_session["teacher_qr_tokens"].values()))

    with app.app_context():
        student_client = app.test_client()
        login(student_client, "2600403")
        dashboard = student_client.get("/alumno")
        csrf_token = re.search(
            rb'name="csrf_token" value="([^"]+)"', dashboard.data
        ).group(1).decode()
        attendance_response = student_client.post(
            "/api/asistencia", data={"csrf_token": csrf_token, "token": token}
        )
        assert attendance_response.status_code == 302
        assert b"Programaci\xc3\xb3n" in student_client.get("/alumno").data

    with app.app_context():
        records = db.session.scalars(
            select(Attendance).where(Attendance.student_id == student_id)
        ).all()
        assert len(records) == 1

    pdf_response = teacher_client.get("/api/cursos/1/asistencias.pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == "application/pdf"
    assert pdf_response.data.startswith(b"%PDF")


def test_student_registration_forces_student_role_and_accepts_short_password(app):
    client = app.test_client()
    page = client.get("/registro")
    csrf_token = re.search(
        rb'name="csrf_token" value="([^"]+)"', page.data
    ).group(1).decode()
    response = client.post(
        "/registro",
        data={
            "csrf_token": csrf_token,
            "name": "Nueva Alumna",
            "email": "nueva@uspg.edu",
            "carnet": "2600403",
            "password": "a",
            "role": "admin",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        user = db.session.scalar(
            select(User).where(User.email == "nueva@uspg.edu")
        )
        assert user.role == "alumno"
        assert user.carnet == "2600403"
        assert user.check_password("a")

    login_page = client.get("/")
    csrf_token = re.search(
        rb'name="csrf_token" value="([^"]+)"', login_page.data
    ).group(1).decode()
    login_response = client.post(
        "/",
        data={"csrf_token": csrf_token, "identifier": "2600403", "password": "a"},
    )
    assert login_response.status_code == 302
    assert login_response.location == "/panel"


def test_seed_admin_accepts_short_password(app, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "short-password-admin@uspg.edu")
    monkeypatch.setenv("ADMIN_PASSWORD", "x")
    result = app.test_cli_runner().invoke(args=["seed-admin"])
    assert result.exit_code == 0
    with app.app_context():
        user = db.session.scalar(
            select(User).where(User.email == "short-password-admin@uspg.edu")
        )
        assert user.check_password("x")


def test_admin_can_see_teacher_student_data_and_attendance(app):
    with app.app_context():
        create_user("Admin", "admin@uspg.edu", "admin")
        teacher = create_user("Docente", "docente@uspg.edu", "docente")
        student = create_user("Alumno", "alumno@uspg.edu", "alumno", "2600403")
        legacy_student = create_user("Alumno anterior", "anterior@uspg.edu", "alumno")
        legacy_student_id = legacy_student.id
        course = Course(name="Programación", code="INF-101", teacher_id=teacher.id)
        db.session.add(course)
        db.session.commit()
        student_id = student.id
        course_id = course.id
        attendance_session = AttendanceSession(
            course_id=course_id,
            token_hash="a" * 64,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
        )
        db.session.add(attendance_session)
        db.session.commit()
        db.session.add(
            Attendance(
                session_id=attendance_session.id,
                student_id=student_id,
                recorded_at=datetime.now(timezone.utc),
            )
        )
        db.session.commit()

    client = app.test_client()
    login(client, "admin@uspg.edu")
    response = client.get("/admin")
    assert response.status_code == 200
    assert b"2600403" in response.data
    assert b"docente@uspg.edu" in response.data
    assert b"INF-101" in response.data
    assert b"Alumno anterior" in response.data
    csrf_token = re.search(
        rb'name="csrf_token" value="([^"]+)"', response.data
    ).group(1).decode()
    assign_response = client.post(
        f"/admin/usuarios/{legacy_student_id}/carnet",
        data={"csrf_token": csrf_token, "carnet": "2600404"},
    )
    assert assign_response.status_code == 302
    with app.app_context():
        migrated_student = db.session.scalar(
            select(User).where(User.email == "anterior@uspg.edu")
        )
        assert migrated_student.carnet == "2600404"