import re
from datetime import datetime, timezone

from sqlalchemy import select

from app import db
from app.models import Attendance, AttendanceSession, Course, CourseEnrollment, User


def create_user(name, email, role, carnet=None):
    user = User(name=name, email=email, role=role, carnet=carnet)
    user.set_password("password-seguro-123")
    db.session.add(user)
    db.session.commit()
    return user


def login(client, identifier, password="password-seguro-123"):
    client.delete_cookie(client.application.config["SESSION_COOKIE_NAME"])
    with client.session_transaction() as client_session:
        client_session.clear()
    page = client.get("/")
    if page.status_code == 302 and page.location == "/panel":
        authenticated_page = client.get(page.location, follow_redirects=True)
        logout_csrf = re.search(
            rb'name="csrf_token" value="([^"]+)"', authenticated_page.data
        ).group(1).decode()
        client.post("/salir", data={"csrf_token": logout_csrf})
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


def test_student_dashboard_calculates_course_alert_thresholds(app):
    with app.app_context():
        teacher = create_user("Docente", "docente@uspg.edu", "docente")
        student = create_user("Alumno", "alumno@uspg.edu", "alumno", "2600403")
        courses = [
            Course(name="Curso bajo", code="LOW-70", teacher_id=teacher.id),
            Course(name="Curso minimo", code="MIN-80", teacher_id=teacher.id),
            Course(name="Curso adecuado", code="OK-90", teacher_id=teacher.id),
        ]
        db.session.add_all(courses)
        db.session.commit()
        now = datetime.now(timezone.utc)
        for course, present_count in zip(courses, (7, 8, 9)):
            for index in range(10):
                attendance_session = AttendanceSession(
                    course_id=course.id,
                    token_hash=f"{course.id}-{index}".ljust(64, "a"),
                    created_at=now,
                    expires_at=now,
                    active=False,
                    closed_at=now,
                )
                db.session.add(attendance_session)
                db.session.flush()
                if index < present_count:
                    db.session.add(
                        Attendance(
                            session_id=attendance_session.id,
                            student_id=student.id,
                            recorded_at=now,
                        )
                    )
        db.session.commit()

    client = app.test_client()
    login(client, "2600403")
    response = client.get("/alumno")

    assert response.status_code == 200
    assert b'data-course-progress="70"' in response.data
    assert b'data-course-progress="80"' in response.data
    assert b'data-course-progress="90"' in response.data
    assert re.findall(rb'data-notice-course="([^"]+)"', response.data) == [
        b"LOW-70",
        b"MIN-80",
    ]
    assert response.data.count(b"notice-item-risk") == 1


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


def test_admin_creates_courses_and_assigns_students(app):
    with app.app_context():
        create_user("Admin", "admin@uspg.edu", "admin")
        teacher = create_user("Docente", "docente@uspg.edu", "docente")
        student = create_user("Alumno", "alumno@uspg.edu", "alumno", "2600403")
        teacher_id, student_id = teacher.id, student.id

    admin_client = app.test_client()
    login(admin_client, "admin@uspg.edu")
    admin_page = admin_client.get("/admin")
    csrf_token = re.search(
        rb'name="csrf_token" value="([^"]+)"', admin_page.data
    ).group(1).decode()
    response = admin_client.post(
        "/admin/cursos",
        data={
            "csrf_token": csrf_token,
            "name": "Biología",
            "code": "BIO-101",
            "teacher_id": str(teacher_id),
            "schedule": "Lunes 08:00–09:30",
            "location_type": "presencial",
            "classroom": "Aula 204",
            "student_ids": [str(student_id)],
        },
    )
    assert response.status_code == 302
    with app.app_context():
        course = db.session.scalar(select(Course).where(Course.code == "BIO-101"))
        assert course.teacher_id == teacher_id
        assert course.schedule == "Lunes 08:00–09:30"
        assert course.classroom == "Aula 204"
        assert [enrollment.student_id for enrollment in course.enrollments] == [
            student_id
        ]

    teacher_client = app.test_client()
    login(teacher_client, "docente@uspg.edu")
    teacher_page = teacher_client.get("/docente")
    teacher_csrf = re.search(
        rb'name="csrf_token" value="([^"]+)"', teacher_page.data
    ).group(1).decode()
    assert b"BIO-101" in teacher_page.data
    assert teacher_client.post(
        "/docente",
        data={"csrf_token": teacher_csrf, "name": "Otro", "code": "OTR-01"},
    ).status_code == 405
    assert teacher_client.post(
        "/admin/cursos", data={"csrf_token": teacher_csrf}
    ).status_code == 403


def test_teacher_session_renewal_close_history_and_notices(app):
    with app.app_context():
        teacher = create_user("Docente", "docente@uspg.edu", "docente")
        alice = create_user("Ana", "ana@uspg.edu", "alumno", "2600401")
        bob = create_user("Beto", "beto@uspg.edu", "alumno", "2600402")
        carol = create_user("Caro", "caro@uspg.edu", "alumno", "2600403")
        course = Course(
            name="Historia", code="HIS-201", teacher_id=teacher.id,
            schedule="Martes 10:00", classroom="Aula 12",
        )
        db.session.add(course)
        db.session.flush()
        students = [alice, bob, carol]
        db.session.add_all(
            [CourseEnrollment(course_id=course.id, student_id=student.id) for student in students]
        )
        db.session.commit()
        alice_id, bob_id, carol_id, course_id = (
            alice.id,
            bob.id,
            carol.id,
            course.id,
        )

    teacher_client = app.test_client()
    login(teacher_client, "docente@uspg.edu")
    dashboard = teacher_client.get("/docente")
    csrf_token = re.search(
        rb'name="csrf_token" value="([^"]+)"', dashboard.data
    ).group(1).decode()
    started = teacher_client.post(
        f"/docente/cursos/{course_id}/sesion", data={"csrf_token": csrf_token}
    )
    assert started.status_code == 302
    session_id = int(started.location.rsplit("/", 1)[-1])
    session_page = teacher_client.get(started.location)
    csrf_token = re.search(
        rb'name="csrf_token" value="([^"]+)"', session_page.data
    ).group(1).decode()
    with teacher_client.session_transaction() as teacher_session:
        old_token = teacher_session["teacher_qr_tokens"][str(session_id)]
    renewed = teacher_client.post(
        f"/docente/sesiones/{session_id}/renovar",
        data={"csrf_token": csrf_token},
    )
    assert renewed.status_code == 302
    with teacher_client.session_transaction() as teacher_session:
        new_token = teacher_session["teacher_qr_tokens"][str(session_id)]
    assert new_token != old_token
    with app.app_context():
        attendance_session = db.session.get(AttendanceSession, session_id)
        remaining = attendance_session.expires_at - datetime.now(timezone.utc).replace(
            tzinfo=None
        )
        assert 4 * 60 < remaining.total_seconds() <= 5 * 60

    alice_client = app.test_client()
    login(alice_client, "2600401")
    student_dashboard = alice_client.get("/alumno")
    student_csrf = re.search(
        rb'name="csrf_token" value="([^"]+)"', student_dashboard.data
    ).group(1).decode()
    checkin = alice_client.post(
        "/api/asistencia",
        data={"csrf_token": student_csrf, "token": new_token},
    )
    assert checkin.status_code == 302
    teacher_client = app.test_client()
    login(teacher_client, "docente@uspg.edu")
    session_page = teacher_client.get(f"/docente/sesiones/{session_id}")
    csrf_token = re.search(
        rb'name="csrf_token" value="([^"]+)"', session_page.data
    ).group(1).decode()

    manual = teacher_client.post(
        f"/docente/sesiones/{session_id}/estudiantes/{carol_id}",
        data={"csrf_token": csrf_token, "status": "justificado"},
    )
    assert manual.status_code == 302
    closed = teacher_client.post(
        f"/docente/sesiones/{session_id}/cerrar",
        data={"csrf_token": csrf_token},
    )
    assert closed.status_code == 302
    status_response = teacher_client.get(f"/docente/sesiones/{session_id}/estado")
    status_by_id = {
        student["id"]: student["status"]
        for student in status_response.get_json()["students"]
    }
    assert status_response.get_json()["closed"] is True
    assert status_by_id == {
        alice_id: "presente",
        bob_id: "ausente",
        carol_id: "justificado",
    }

    history = teacher_client.get(
        f"/docente/historial?curso={course_id}&estado=ausente"
    )
    assert b"Beto" in history.data
    assert b"Ana" not in history.data
    csrf_token = re.search(
        rb'name="csrf_token" value="([^"]+)"', history.data
    ).group(1).decode()
    with app.app_context():
        bob_record = db.session.scalar(
            select(Attendance).where(
                Attendance.session_id == session_id,
                Attendance.student_id == bob_id,
            )
        )
        bob_record_id = bob_record.id
    correction = teacher_client.post(
        f"/docente/historial/{bob_record_id}",
        data={"csrf_token": csrf_token, "status": "justificado"},
    )
    assert correction.status_code == 302

    notice = teacher_client.post(
        "/docente/avisos",
        data={
            "csrf_token": csrf_token,
            "course_id": str(course_id),
            "message": "La clase empieza 20 minutos después.",
        },
    )
    assert notice.status_code == 302
    alice_client = app.test_client()
    login(alice_client, "2600401")
    student_page = alice_client.get("/alumno")
    assert "La clase empieza 20 minutos después.".encode() in student_page.data