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
            "schedule": "Martes 10:00",
            "location_type": "presencial",
            "classroom": "B-2",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        course = db.session.scalar(select(Course).where(Course.code == "BD-101"))
        assert course is not None
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


def test_admin_student_summary_and_audit_page_load(
    app, sample_data, login_as
):
    client = app.test_client()
    login_as(client, sample_data["admin_id"])

    assert client.get("/admin/estudiantes").status_code == 200
    audit = client.get("/admin/auditoria")
    assert audit.status_code == 200
