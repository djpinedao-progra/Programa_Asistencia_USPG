import re
from datetime import datetime, timezone

from sqlalchemy import select

from app import db
from app.models import Attendance, AttendanceSession, Course, CourseEnrollment, User
from app.repositories import CourseRepository


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
    assert b"Resumen acad\xc3\xa9mico" in response.data
    students_page = client.get("/admin/estudiantes")
    teachers_page = client.get("/admin/docentes")
    courses_page = client.get("/admin/cursos")
    assert students_page.status_code == 200
    assert teachers_page.status_code == 200
    assert courses_page.status_code == 200
    assert b"2600403" in students_page.data
    assert b"Alumno anterior" in students_page.data
    assert b"docente@uspg.edu" in teachers_page.data
    assert b"INF-101" in courses_page.data
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


def test_admin_filters_profiles_and_course_availability(app):
    with app.app_context():
        create_user("Admin", "admin@uspg.edu", "admin")
        teacher = create_user("Docente Uno", "docente@uspg.edu", "docente")
        student = create_user("Estudiante Uno", "alumno@uspg.edu", "alumno", "2600401")
        course = Course(
            name="Química", code="QUI-101", teacher_id=teacher.id,
            schedule="Jueves 09:00", classroom="Lab 2",
        )
        db.session.add(course)
        db.session.flush()
        db.session.add(CourseEnrollment(course_id=course.id, student_id=student.id))
        db.session.commit()
        student_id, teacher_id, course_id = student.id, teacher.id, course.id

    client = app.test_client()
    login(client, "admin@uspg.edu")
    students_page = client.get(f"/admin/estudiantes?q=2600401&curso={course_id}")
    assert students_page.status_code == 200
    assert b"Estudiante Uno" in students_page.data
    assert b"QUI-101" in students_page.data
    profile_page = client.get(f"/admin/usuarios/{student_id}/perfil")
    csrf_token = re.search(
        rb'name="csrf_token" value="([^"]+)"', profile_page.data
    ).group(1).decode()
    update = client.post(
        f"/admin/usuarios/{student_id}/perfil",
        data={
            "csrf_token": csrf_token,
            "name": "Estudiante Actualizado",
            "email": "actualizado@uspg.edu",
            "carnet": "2600402",
        },
    )
    assert update.status_code == 302
    with app.app_context():
        student = db.session.get(User, student_id)
        assert student.name == "Estudiante Actualizado"
        assert student.email == "actualizado@uspg.edu"
        assert student.carnet == "2600402"

    teacher_page = client.get("/admin/docentes?q=docente%40uspg.edu")
    assert b"Docente Uno" in teacher_page.data
    course_page = client.get(f"/admin/cursos?docente={teacher_id}")
    assert b"QUI-101" in course_page.data
    toggle_csrf = re.search(
        rb'name="csrf_token" value="([^"]+)"', course_page.data
    ).group(1).decode()
    course_update = client.post(
        f"/admin/cursos/{course_id}/asignaciones",
        data={
            "csrf_token": toggle_csrf,
            "name": "Química orgánica",
            "code": "QUI-102",
            "teacher_id": str(teacher_id),
            "schedule": "Jueves 10:00",
            "location_type": "presencial",
            "classroom": "Lab 3",
            "student_ids": [str(student_id)],
            "is_active": "on",
        },
    )
    assert course_update.status_code == 302
    with app.app_context():
        updated_course = db.session.get(Course, course_id)
        assert updated_course.name == "Química orgánica"
        assert updated_course.code == "QUI-102"
        assert updated_course.schedule == "Jueves 10:00"
    disabled = client.post(
        f"/admin/cursos/{course_id}/estado", data={"csrf_token": toggle_csrf}
    )
    assert disabled.status_code == 302
    with app.app_context():
        assert db.session.get(Course, course_id).is_active is False
        assert CourseRepository().list_for_teacher(teacher_id) == []
    reenabled = client.post(
        f"/admin/cursos/{course_id}/estado",
        data={"csrf_token": toggle_csrf, "is_active": "on"},
    )
    assert reenabled.status_code == 302
    with app.app_context():
        assert len(CourseRepository().list_for_teacher(teacher_id)) == 1


def test_admin_attendance_reports_and_session_pdf(app):
    with app.app_context():
        create_user("Admin", "admin@uspg.edu", "admin")
        teacher = create_user("Docente", "docente@uspg.edu", "docente")
        student = create_user("Alumna", "alumna@uspg.edu", "alumno", "2600403")
        course = Course(
            name="Literatura", code="LIT-101", teacher_id=teacher.id,
            schedule="Viernes 11:00", classroom="Aula 7",
        )
        db.session.add(course)
        db.session.flush()
        db.session.add(CourseEnrollment(course_id=course.id, student_id=student.id))
        db.session.flush()
        now = datetime.now(timezone.utc)
        attendance_session = AttendanceSession(
            course_id=course.id,
            token_hash="b" * 64,
            created_at=now,
            expires_at=now,
            active=False,
            closed_at=now,
        )
        db.session.add(attendance_session)
        db.session.flush()
        db.session.add(
            Attendance(
                session_id=attendance_session.id,
                student_id=student.id,
                recorded_at=now,
                status="presente",
                source="qr",
            )
        )
        db.session.commit()
        course_id, teacher_id = course.id, teacher.id
        session_id = attendance_session.id
        session_date = now.date().isoformat()

    client = app.test_client()
    login(client, "admin@uspg.edu")
    filtered_attendance = client.get(
        f"/admin/asistencias?curso={course_id}&fecha={session_date}&estudiante=2600403&riesgo=ninguno"
    )
    assert filtered_attendance.status_code == 200
    assert b"Alumna" in filtered_attendance.data
    assert b"100%" in filtered_attendance.data
    report_page = client.get(f"/admin/reportes?curso={course_id}")
    assert report_page.status_code == 200
    assert b"LIT-101" in report_page.data
    report_pdf = client.get(f"/admin/reportes.pdf?curso={course_id}")
    assert report_pdf.status_code == 200
    assert report_pdf.mimetype == "application/pdf"
    assert report_pdf.data.startswith(b"%PDF")
    history = client.get(
        f"/admin/historial?curso={course_id}&docente={teacher_id}&fecha={session_date}"
    )
    assert history.status_code == 200
    assert b"1/1" in history.data
    session_pdf = client.get(f"/admin/sesiones/{session_id}/reporte.pdf")
    assert session_pdf.status_code == 200
    assert session_pdf.mimetype == "application/pdf"
    assert session_pdf.data.startswith(b"%PDF")