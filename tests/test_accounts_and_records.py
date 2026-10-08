import re
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app import db
from app.models import (
    Attendance,
    AttendanceSession,
    Course,
    CourseEnrollment,
    PasswordReplacement,
    User,
)
from app.services import UserService


def create_user(name, email, role, carnet=None, password="clave-actual"):
    user = User(name=name, email=email, role=role, carnet=carnet)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def csrf(client, path="/"):
    from flask import g

    # The fixture keeps one app context open, so Flask-Login's cached user must be cleared.
    g.pop("_login_user", None)
    return re.search(rb'name="csrf_token" value="([^"]+)"', client.get(path).data).group(1).decode()


def post_login(client, identifier, password):
    return client.post("/", data={"csrf_token": csrf(client), "identifier": identifier, "password": password})


@pytest.mark.parametrize(
    "email,role",
    [
        ("ana@alumno.uspg.edu.gt", "alumno"),
        ("profe@catedratico.uspg.edu.gt", "docente"),
        ("jefa@administrador.uspg.edu.gt", "admin"),
        (" ANA@ALUMNO.USPG.EDU.GT ", "alumno"),
        ("ana@uspg.edu", None),
        ("ana@gmail.com", None),
        ("no-es-correo", None),
    ],
)
def test_email_domain_defines_role(email, role):
    assert UserService.email_role(email) == role


def test_account_creation_rejects_domain_of_another_role(app):
    with pytest.raises(ValueError, match="@catedratico.uspg.edu.gt"):
        UserService().create_user("Profe", "profe@alumno.uspg.edu.gt", "x", "docente")
    student = UserService().register_student("Ana", "ana@alumno.uspg.edu.gt", "2600010", "a")
    assert student.role == "alumno"


def test_login_rejects_account_whose_domain_does_not_match_role(app):
    create_user("Ana", "ana@uspg.edu", "alumno", "2600010")
    response = post_login(app.test_client(), "ana@uspg.edu", "clave-actual")
    assert response.status_code == 200
    assert "Correo o contraseña incorrectos".encode() in response.data


def test_session_is_closed_if_account_domain_stops_matching(app):
    user = create_user("Ana", "ana@alumno.uspg.edu.gt", "alumno", "2600010")
    client = app.test_client()
    assert post_login(client, "ana@alumno.uspg.edu.gt", "clave-actual").status_code == 302
    user.email = "ana@uspg.edu"
    db.session.commit()
    assert client.get("/alumno").status_code == 403
    assert client.get("/alumno").status_code == 302


def test_recovery_sends_temporary_password_that_replaces_old_one_once(app):
    user = create_user("Ana", "ana@alumno.uspg.edu.gt", "alumno", "2600010")
    client = app.test_client()
    sent = {}
    with patch("app.recovery.send_password", side_effect=lambda email, password: sent.update(email=email, password=password)):
        response = client.post(
            "/recuperar-contrasena",
            data={"csrf_token": csrf(client, "/recuperar-contrasena"), "email": " ANA@alumno.uspg.edu.gt "},
        )
        assert response.status_code == 302
        client.post(
            "/recuperar-contrasena",
            data={"csrf_token": csrf(client, "/recuperar-contrasena"), "email": "ana@alumno.uspg.edu.gt"},
        )
    assert sent["email"] == "ana@alumno.uspg.edu.gt"
    pending = db.session.get(PasswordReplacement, user.id)
    assert pending is not None and pending.password_hash != sent["password"]

    assert post_login(app.test_client(), "ana@alumno.uspg.edu.gt", sent["password"]).status_code == 302
    db.session.expire_all()
    assert db.session.get(PasswordReplacement, user.id) is None
    assert db.session.get(User, user.id).check_password(sent["password"])
    assert post_login(app.test_client(), "ana@alumno.uspg.edu.gt", "clave-actual").status_code == 200


def test_recovery_is_silent_for_unknown_accounts_and_keeps_password_when_mail_fails(app):
    user = create_user("Ana", "ana@alumno.uspg.edu.gt", "alumno", "2600010")
    client = app.test_client()
    with patch("app.recovery.send_password") as send:
        response = client.post(
            "/recuperar-contrasena",
            data={"csrf_token": csrf(client, "/recuperar-contrasena"), "email": "nadie@alumno.uspg.edu.gt"},
            follow_redirects=True,
        )
    send.assert_not_called()
    assert "Si el correo pertenece a una cuenta".encode() in response.data

    with patch("app.recovery.send_password", side_effect=OSError("smtp caído")):
        client.post(
            "/recuperar-contrasena",
            data={"csrf_token": csrf(client, "/recuperar-contrasena"), "email": "ana@alumno.uspg.edu.gt"},
        )
    assert db.session.get(PasswordReplacement, user.id) is None
    assert post_login(app.test_client(), "ana@alumno.uspg.edu.gt", "clave-actual").status_code == 302


def test_expired_temporary_password_is_rejected(app):
    user = create_user("Ana", "ana@alumno.uspg.edu.gt", "alumno", "2600010")
    from werkzeug.security import generate_password_hash

    now = datetime.now(timezone.utc)
    db.session.add(
        PasswordReplacement(
            user_id=user.id,
            password_hash=generate_password_hash("temporal"),
            requested_at=now - timedelta(minutes=20),
            expires_at=now - timedelta(minutes=5),
        )
    )
    db.session.commit()
    assert post_login(app.test_client(), "ana@alumno.uspg.edu.gt", "temporal").status_code == 200


def _course_with_closed_session(student_status):
    teacher = create_user("Profe", "profe@catedratico.uspg.edu.gt", "docente")
    student = create_user("Ana", "ana@alumno.uspg.edu.gt", "alumno", "2600010")
    course = Course(name="Historia", code="HIS-101", teacher_id=teacher.id)
    db.session.add(course)
    db.session.flush()
    db.session.add(CourseEnrollment(course_id=course.id, student_id=student.id))
    created = datetime.now(timezone.utc) - timedelta(days=1)
    attendance_session = AttendanceSession(
        course_id=course.id, token_hash="a" * 64, created_at=created,
        expires_at=created + timedelta(minutes=5), active=False, closed_at=created + timedelta(hours=1),
    )
    db.session.add(attendance_session)
    db.session.flush()
    attendance = Attendance(
        session_id=attendance_session.id, student_id=student.id,
        recorded_at=created, status=student_status, source="qr",
    )
    db.session.add(attendance)
    db.session.commit()
    return teacher, student, attendance


def test_student_dashboard_counts_justified_separately_from_absences(app):
    _course_with_closed_session("justificado")
    client = app.test_client()
    post_login(client, "ana@alumno.uspg.edu.gt", "clave-actual")
    page = client.get("/alumno").get_data(as_text=True)
    assert "<strong>0</strong> faltas" in page
    assert "<strong>1</strong> justificadas" in page


def test_teacher_correction_keeps_original_recording_time(app):
    teacher, student, attendance = _course_with_closed_session("ausente")
    original_time = attendance.recorded_at
    client = app.test_client()
    post_login(client, "profe@catedratico.uspg.edu.gt", "clave-actual")
    response = client.post(
        f"/docente/historial/{attendance.id}",
        data={"csrf_token": csrf(client, "/docente/historial"), "status": "justificado"},
    )
    assert response.status_code == 302
    db.session.expire_all()
    corrected = db.session.get(Attendance, attendance.id)
    assert corrected.status == "justificado"
    assert corrected.recorded_at.replace(tzinfo=None) == original_time.replace(tzinfo=None)
    assert corrected.modified_at is not None
