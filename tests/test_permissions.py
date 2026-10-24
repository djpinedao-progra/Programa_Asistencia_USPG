import pytest


@pytest.mark.parametrize(
    ("path", "required_role"),
    [
        ("/admin", "admin"),
        ("/admin/estudiantes", "admin"),
        ("/admin/docentes", "admin"),
        ("/admin/usuarios/{student_id}/perfil", "admin"),
        ("/admin/cursos", "admin"),
        ("/admin/cursos/importar", "admin"),
        ("/admin/cursos/importar/plantilla.csv", "admin"),
        ("/admin/asistencias", "admin"),
        ("/admin/reportes", "admin"),
        ("/admin/historial", "admin"),
        ("/admin/auditoria", "admin"),
        ("/admin/reportes.pdf", "admin"),
        ("/admin/sesiones/{session_id}/reporte.pdf", "admin"),
        ("/docente", "docente"),
        ("/docente/cursos/{course_id}", "docente"),
        ("/docente/estudiantes", "docente"),
        ("/docente/historial", "docente"),
        ("/docente/sesiones/{session_id}", "docente"),
        ("/docente/sesiones/{session_id}/estado", "docente"),
        ("/alumno", "alumno"),
        ("/check-in", "alumno"),
    ],
)
def test_role_protected_pages_redirect_for_anonymous_and_reject_wrong_role(
    app, sample_data, login_as, path, required_role
):
    ids = sample_data
    path = path.format(
        student_id=ids["student_id"],
        course_id=ids["course_id"],
        session_id=ids["closed_session_id"],
    )
    client = app.test_client()

    assert client.get(path).status_code == 302

    wrong_role_id = (
        ids["teacher_id"] if required_role == "admin"
        else ids["admin_id"] if required_role == "docente"
        else ids["admin_id"]
    )
    login_as(client, wrong_role_id)
    assert client.get(path).status_code == 403

    correct_role_id = {
        "admin": ids["admin_id"],
        "docente": ids["teacher_id"],
        "alumno": ids["student_id"],
    }[required_role]
    login_as(client, correct_role_id)
    assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    ("role_id", "path", "expected_home"),
    [
        ("admin_id", "/admin", "/admin"),
        ("teacher_id", "/docente", "/docente"),
        ("student_id", "/alumno", "/alumno"),
    ],
)
def test_sidebar_logo_links_to_current_role_dashboard(
    app, sample_data, login_as, role_id, path, expected_home
):
    client = app.test_client()
    login_as(client, sample_data[role_id])

    response = client.get(path)

    assert response.status_code == 200
    assert f'class="sidebar-brand" href="{expected_home}"' in response.text
