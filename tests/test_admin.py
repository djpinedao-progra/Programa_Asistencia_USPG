import pytest
from sqlalchemy import select

from app import db
from app.models import AuditLog, Course, CourseEnrollment


def test_admin_can_create_course_and_import_valid_enrollment(
    app, sample_data, login_as, csrf_token
):
    ids = sample_data
    client = app.test_client()
    login_as(client, ids["admin_id"])
    token = csrf_token(client)

    response = client.post(
        "/admin/cursos",
        data={
            "csrf_token": token,
            "name": "Bases de datos",
            "code": "bd-101",
            "teacher_id": str(ids["teacher_id"]),
            "schedule_days": ["Martes"],
            "start_time": "10:00",
            "end_time": "11:30",
            "location_type": "presencial",
            "classroom": "Salón 2",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        course = db.session.scalar(select(Course).where(Course.code == "BD-101"))
        assert course is not None
        assert course.schedule == "Martes, 10:00–11:30"
        assert course.classroom == "Salón 2"
        assert db.session.scalar(
            select(AuditLog).where(
                AuditLog.action == "course_created",
                AuditLog.entity_id == course.id,
            )
        ) is not None
        course_id = course.id

    imported = client.post(
        "/admin/cursos/importar",
        data={
            "csrf_token": token,
            "action": "import",
            "course_code": ["BD-101", "INVALID"],
            "carnet": ["2600001", "2600002"],
        },
    )
    assert imported.status_code == 200
    assert "Matriculado" in imported.text
    assert "Curso no encontrado" in imported.text
    with app.app_context():
        enrollment = db.session.scalar(
            select(CourseEnrollment).where(
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.student_id == ids["student_id"],
            )
        )
        assert enrollment is not None


def test_classroom_list_and_schedule_conflicts(
    app, sample_data, login_as, csrf_token
):
    client = app.test_client()
    login_as(client, sample_data["admin_id"])
    token = csrf_token(client)

    page = client.get("/admin/cursos")
    assert page.status_code == 200
    for number in range(1, 26):
        assert f'value="Salón {number}"' in page.text
    assert 'value="Salón 26"' not in page.text

    base_data = {
        "csrf_token": token,
        "teacher_id": str(sample_data["teacher_id"]),
        "schedule_days": ["Martes", "Miércoles"],
        "start_time": "08:00",
        "end_time": "09:30",
        "location_type": "presencial",
        "classroom": "Salón 5",
    }
    created = client.post(
        "/admin/cursos",
        data={**base_data, "name": "Curso A", "code": "ROOM-A"},
    )
    assert created.status_code == 302
    with app.app_context():
        course_a_id = db.session.scalar(
            select(Course.id).where(Course.code == "ROOM-A")
        )

    unchanged = client.post(
        f"/admin/cursos/{course_a_id}/asignaciones",
        data={
            **base_data,
            "name": "Curso A",
            "code": "ROOM-A",
            "is_active": "on",
        },
        follow_redirects=True,
    )
    assert "Asignación del curso actualizada" in unchanged.text

    conflict = client.post(
        "/admin/cursos",
        data={
            **base_data,
            "name": "Curso B",
            "code": "ROOM-B",
            "schedule_days": ["Miércoles"],
            "start_time": "09:00",
            "end_time": "10:00",
        },
        follow_redirects=True,
    )
    assert "Salón 5 ya está ocupado" in conflict.text
    with app.app_context():
        assert (
            db.session.scalar(select(Course).where(Course.code == "ROOM-B"))
            is None
        )

    invalid_room = client.post(
        "/admin/cursos",
        data={
            **base_data,
            "name": "Curso fuera de catálogo",
            "code": "ROOM-INVALID",
            "classroom": "Auditorio",
        },
        follow_redirects=True,
    )
    assert "Selecciona uno de los 25 salones disponibles" in invalid_room.text

    adjacent = client.post(
        "/admin/cursos",
        data={
            **base_data,
            "name": "Curso C",
            "code": "ROOM-C",
            "schedule_days": ["Miércoles"],
            "start_time": "09:30",
            "end_time": "10:30",
        },
    )
    assert adjacent.status_code == 302
    with app.app_context():
        assert db.session.scalar(select(Course).where(Course.code == "ROOM-C"))


def test_virtual_course_does_not_require_classroom(
    app, sample_data, login_as, csrf_token
):
    client = app.test_client()
    login_as(client, sample_data["admin_id"])
    token = csrf_token(client)
    response = client.post(
        "/admin/cursos",
        data={
            "csrf_token": token,
            "name": "Curso virtual",
            "code": "VIRTUAL-1",
            "teacher_id": str(sample_data["teacher_id"]),
            "schedule_days": ["Viernes"],
            "start_time": "18:00",
            "end_time": "20:00",
            "location_type": "virtual",
            "classroom": "",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        course = db.session.scalar(
            select(Course).where(Course.code == "VIRTUAL-1")
        )
        assert course.classroom == "Virtual"


def test_admin_rejects_overlapping_teacher_schedule_on_create_and_update(
    app, sample_data, login_as, csrf_token
):
    client = app.test_client()
    login_as(client, sample_data["admin_id"])
    token = csrf_token(client)
    base_data = {
        "csrf_token": token,
        "teacher_id": str(sample_data["teacher_id"]),
        "schedule_days": ["Sábado"],
        "location_type": "presencial",
    }
    first = client.post(
        "/admin/cursos",
        data={
            **base_data,
            "name": "Curso base docente",
            "code": "DOC-A",
            "start_time": "07:30",
            "end_time": "08:30",
            "classroom": "Salón 1",
        },
    )
    assert first.status_code == 302

    overlap = client.post(
        "/admin/cursos",
        data={
            **base_data,
            "name": "Curso superpuesto",
            "code": "DOC-B",
            "start_time": "08:00",
            "end_time": "09:00",
            "classroom": "Salón 2",
        },
        follow_redirects=True,
    )
    assert "El docente ya imparte DOC-A" in overlap.text

    adjacent = client.post(
        "/admin/cursos",
        data={
            **base_data,
            "name": "Curso contiguo",
            "code": "DOC-C",
            "start_time": "08:30",
            "end_time": "09:30",
            "classroom": "Salón 2",
        },
    )
    assert adjacent.status_code == 302
    with app.app_context():
        course = db.session.scalar(select(Course).where(Course.code == "DOC-C"))
        course_id = course.id

    update = client.post(
        f"/admin/cursos/{course_id}/asignaciones",
        data={
            **base_data,
            "name": "Curso contiguo",
            "code": "DOC-C",
            "start_time": "08:15",
            "end_time": "09:30",
            "classroom": "Salón 2",
            "is_active": "on",
        },
        follow_redirects=True,
    )
    assert "El docente ya imparte DOC-A" in update.text
    with app.app_context():
        course = db.session.get(Course, course_id)
        assert course.schedule.endswith("08:30–09:30")


def test_create_course_validation_preserves_submitted_values(
    app, sample_data, login_as, csrf_token
):
    client = app.test_client()
    login_as(client, sample_data["admin_id"])
    response = client.post(
        "/admin/cursos",
        data={
            "csrf_token": csrf_token(client),
            "name": "Curso conservado",
            "code": "PROG-1",
            "teacher_id": str(sample_data["teacher_id"]),
            "schedule_days": ["Viernes"],
            "start_time": "14:00",
            "end_time": "16:00",
            "location_type": "presencial",
            "classroom": "Salón 7",
            "student_ids": [str(sample_data["student_id"])],
        },
    )

    assert response.status_code == 400
    assert response.request.path == "/admin/cursos"
    assert 'value="Curso conservado"' in response.text
    assert 'value="PROG-1"' in response.text
    assert 'value="14:00"' in response.text
    assert 'value="Salón 7" selected' in response.text
    assert 'value="Viernes" checked' in response.text
    assert "Ese código de curso ya está registrado" in response.text
    assert 'class="field-error" role="alert"' in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/admin/docentes?q=SinCoincidencias",
        "/admin/estudiantes?q=SinCoincidencias",
        "/admin/cursos?q=SinCoincidencias",
    ],
)
def test_admin_directories_distinguish_search_without_results(
    app, sample_data, login_as, path
):
    client = app.test_client()
    login_as(client, sample_data["admin_id"])

    response = client.get(path)

    assert response.status_code == 200
    assert "No hay resultados para «SinCoincidencias»" in response.text
    assert "No hay docentes registrados" not in response.text
    assert "No hay estudiantes registrados" not in response.text
    assert "No hay cursos registrados" not in response.text


def test_admin_student_summary_and_audit_page_load(
    app, sample_data, login_as
):
    client = app.test_client()
    login_as(client, sample_data["admin_id"])

    assert client.get("/admin/estudiantes").status_code == 200
    audit = client.get("/admin/auditoria")
    assert audit.status_code == 200
