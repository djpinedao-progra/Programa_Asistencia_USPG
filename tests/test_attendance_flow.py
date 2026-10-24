import hashlib
from datetime import datetime, timedelta, timezone

from flask import g
from sqlalchemy import select

from app import db
from app.models import Attendance, AttendanceSession, Course, CourseEnrollment
from app.services.attendance_service import AttendanceService


def _login(client, csrf_token, identifier, expected_path):
    g.pop("_login_user", None)
    response = client.post(
        "/",
        data={
            "csrf_token": csrf_token(client),
            "identifier": identifier,
            "password": "Password123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert response.request.path == expected_path
    return response


def test_admin_teacher_and_student_complete_attendance_workflow(
    app, sample_data, csrf_token
):
    ids = sample_data

    teacher = app.test_client()
    teacher_home = _login(
        teacher, csrf_token, "docente@catedratico.uspg.edu.gt", "/docente"
    )
    assert b"Tomar asistencia" in teacher_home.data

    started = teacher.post(
        f"/docente/cursos/{ids['course_id']}/sesion",
        data={"csrf_token": csrf_token(teacher)},
        follow_redirects=True,
    )
    assert started.status_code == 200
    assert b"data:image/png;base64," in started.data
    assert b"05:00" in started.data

    with teacher.session_transaction() as session:
        session_id, qr_token = next(
            (int(key), value)
            for key, value in session["teacher_qr_tokens"].items()
        )

    with app.app_context():
        attendance_session = db.session.get(AttendanceSession, session_id)
        duration = attendance_session.expires_at - attendance_session.created_at
        assert timedelta(minutes=4, seconds=59) <= duration <= timedelta(minutes=5)

    initial_status = teacher.get(f"/docente/sesiones/{session_id}/estado")
    assert initial_status.status_code == 200
    assert initial_status.json["present_count"] == 0
    assert initial_status.json["students"] == [
        {
            "id": ids["student_id"],
            "recorded_at": None,
            "source": None,
            "status": "pendiente",
        }
    ]

    previous_qr_token = qr_token
    renewed = teacher.post(
        f"/docente/sesiones/{session_id}/renovar",
        data={"csrf_token": csrf_token(teacher)},
        follow_redirects=True,
    )
    assert renewed.status_code == 200
    assert b"data:image/png;base64," in renewed.data
    assert b"05:00" in renewed.data
    with teacher.session_transaction() as session:
        qr_token = session["teacher_qr_tokens"][str(session_id)]
    assert qr_token != previous_qr_token

    student = app.test_client()
    student_home = _login(student, csrf_token, "2600001", "/alumno")
    assert b"Escanear QR" in student_home.data

    invalidated = student.post(
        "/api/asistencia",
        data={"csrf_token": csrf_token(student), "token": previous_qr_token},
        follow_redirects=True,
    )
    assert invalidated.status_code == 200
    with app.app_context():
        assert not db.session.scalars(
            select(Attendance).where(Attendance.session_id == session_id)
        ).all()

    confirmation = student.get(f"/check-in?token={qr_token}")
    assert confirmation.status_code == 200
    assert qr_token.encode() in confirmation.data

    registered = student.post(
        "/api/asistencia",
        data={"csrf_token": csrf_token(student), "token": qr_token},
        follow_redirects=True,
    )
    assert registered.status_code == 200
    assert b"Asistencia registrada" in registered.data

    g.pop("_login_user", None)
    live_status = teacher.get(f"/docente/sesiones/{session_id}/estado")
    assert live_status.status_code == 200
    assert live_status.json["present_count"] == 1
    assert live_status.json["students"][0]["status"] == "presente"
    assert live_status.json["students"][0]["source"] == "qr"
    assert live_status.json["students"][0]["recorded_at"]

    g.pop("_login_user", None)
    manually_confirmed = teacher.post(
        f"/docente/sesiones/{session_id}/estudiantes/{ids['student_id']}",
        data={"csrf_token": csrf_token(teacher), "status": "presente"},
        follow_redirects=True,
    )
    assert manually_confirmed.status_code == 200
    g.pop("_login_user", None)
    manual_status = teacher.get(f"/docente/sesiones/{session_id}/estado")
    assert manual_status.json["present_count"] == 1
    assert manual_status.json["students"][0]["source"] == "manual"

    g.pop("_login_user", None)
    student.post(
        "/api/asistencia",
        data={"csrf_token": csrf_token(student), "token": qr_token},
    )
    with app.app_context():
        records = db.session.scalars(
            select(Attendance).where(Attendance.session_id == session_id)
        ).all()
        assert len(records) == 1

    g.pop("_login_user", None)
    closed = teacher.post(
        f"/docente/sesiones/{session_id}/cerrar",
        data={"csrf_token": csrf_token(teacher)},
        follow_redirects=True,
    )
    assert closed.status_code == 200
    assert b"La asistencia est" in closed.data

    g.pop("_login_user", None)
    rejected_after_close = student.post(
        "/api/asistencia",
        data={"csrf_token": csrf_token(student), "token": qr_token},
        follow_redirects=True,
    )
    assert rejected_after_close.status_code == 200

    admin = app.test_client()
    admin_home = _login(
        admin, csrf_token, "admin@administrador.uspg.edu.gt", "/admin"
    )
    assert b"Panel" in admin_home.data or b"Administr" in admin_home.data
    overview = admin.get("/admin/asistencias")
    history = admin.get("/admin/historial")
    assert overview.status_code == 200
    assert history.status_code == 200
    assert b"PROG-1" in history.data


def test_qr_attendance_flow_duplicate_expiry_and_missing_students(
    app, sample_data, login_as, csrf_token
):
    ids = sample_data
    with app.app_context():
        db.session.add(
            CourseEnrollment(
                course_id=ids["course_id"],
                student_id=ids["other_student_id"],
            )
        )
        db.session.commit()

    teacher = app.test_client()
    login_as(teacher, ids["teacher_id"])
    token = csrf_token(teacher)
    started = teacher.post(
        f"/docente/cursos/{ids['course_id']}/sesion",
        data={"csrf_token": token},
        follow_redirects=True,
    )
    assert started.status_code == 200
    with teacher.session_transaction() as session:
        session_id, qr_token = next(
            (int(key), value)
            for key, value in session["teacher_qr_tokens"].items()
        )

    student = app.test_client()
    login_as(student, ids["student_id"])
    student_csrf = csrf_token(student)
    present = student.post(
        "/api/asistencia",
        data={"csrf_token": student_csrf, "token": qr_token},
    )
    assert present.status_code == 302

    duplicate = student.post(
        "/api/asistencia",
        data={"csrf_token": student_csrf, "token": qr_token},
    )
    assert duplicate.status_code == 302
    with app.app_context():
        rows = db.session.scalars(
            select(Attendance).where(Attendance.session_id == session_id)
        ).all()
        assert len(rows) == 1
        assert rows[0].student_id == ids["student_id"]

    outsider = app.test_client()
    login_as(outsider, ids["outsider_id"])
    outsider_csrf = csrf_token(outsider)
    rejected = outsider.post(
        "/api/asistencia",
        data={"csrf_token": outsider_csrf, "token": qr_token},
    )
    assert rejected.status_code == 302

    with app.app_context():
        attendance_session = db.session.get(AttendanceSession, session_id)
        attendance_session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()
    expired = student.post(
        "/api/asistencia",
        data={"csrf_token": student_csrf, "token": qr_token},
    )
    assert expired.status_code == 302

    login_as(teacher, ids["teacher_id"])
    closed = teacher.post(
        f"/docente/sesiones/{session_id}/cerrar",
        data={"csrf_token": token},
    )
    assert closed.status_code == 302
    with app.app_context():
        absent = db.session.scalar(
            select(Attendance).where(
                Attendance.session_id == session_id,
                Attendance.student_id == ids["other_student_id"],
            )
        )
        assert absent is not None
        assert absent.status == "ausente"


def test_session_auto_closes_after_course_schedule_and_rejects_new_marks(
    app, sample_data
):
    raw_token = "automatic-close-token"
    with app.app_context():
        course = db.session.get(Course, sample_data["course_id"])
        course.schedule = "Martes, 08:00–09:00"
        opened_at = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)
        attendance_session = AttendanceSession(
            course_id=course.id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            created_at=opened_at,
            expires_at=datetime(2026, 10, 20, 18, 0, tzinfo=timezone.utc),
            active=True,
        )
        db.session.add(attendance_session)
        db.session.commit()

        service = AttendanceService(
            auto_close_grace_minutes=30,
            timezone_name="America/Guatemala",
        )
        assert service.automatic_close_deadline(attendance_session) == datetime(
            2026, 10, 20, 15, 30, tzinfo=timezone.utc
        )
        assert service.close_expired_sessions(
            datetime(2026, 10, 20, 15, 31, tzinfo=timezone.utc)
        ) == 1
        assert attendance_session.active is False
        assert attendance_session.closed_at.replace(tzinfo=timezone.utc) == datetime(
            2026, 10, 20, 15, 31, tzinfo=timezone.utc
        )
        absence = db.session.scalar(
            select(Attendance).where(
                Attendance.session_id == attendance_session.id,
                Attendance.student_id == sample_data["student_id"],
            )
        )
        assert absence.status == "ausente"

        student = absence.student
        try:
            service.record_attendance(raw_token, student)
        except ValueError as error:
            assert "no está activa" in str(error)
        else:
            raise AssertionError("Una sesión cerrada aceptó una nueva marca")
