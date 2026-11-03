from app.services import UserService


def _enable_google(app):
    app.config.update(
        GOOGLE_CLASSROOM_ENABLED=True,
        GOOGLE_CLIENT_ID="client-id",
        GOOGLE_CLIENT_SECRET="client-secret",
        GOOGLE_REDIRECT_URI="https://staging.example/admin/google/callback",
        GOOGLE_TOKEN_ENCRYPTION_KEY="test-encryption-secret",
    )


def test_test_user_can_open_only_google_classroom_area(app, sample_data, login_as):
    _enable_google(app)
    with app.app_context():
        tester = UserService().create_user(
            "Analista de pruebas",
            "analista@alumno.uspg.edu.gt",
            "Password123!",
            "alumno",
            carnet="9900001",
            google_classroom_access=True,
        )
        tester_id = tester.id

    client = app.test_client()
    login_as(client, tester_id)

    assert client.get("/admin").status_code == 403
    assert client.get("/admin/google").status_code == 200
    assert b"Google Classroom" in client.get("/alumno").data


def test_catedratico_can_be_created_as_administrator_by_an_admin(app, csrf_token):
    with app.app_context():
        user = UserService().create_user(
            "V. Gutiérrez",
            "vgutierrez@catedratico.uspg.edu.gt",
            "Password123!",
            "admin",
        )
        assert user.role == "admin"

    client = app.test_client()
    response = client.post(
        "/",
        data={
            "csrf_token": csrf_token(client),
            "identifier": "vgutierrez@catedratico.uspg.edu.gt",
            "password": "Password123!",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/panel")


def test_plain_student_cannot_open_google_classroom(app, sample_data, login_as):
    _enable_google(app)
    client = app.test_client()
    login_as(client, sample_data["student_id"])

    assert client.get("/admin/google").status_code == 403


def test_admin_can_grant_limited_google_access_to_existing_student(
    app, sample_data
):
    with app.app_context():
        user = UserService().update_google_classroom_access(
            sample_data["student_id"], True, actor_id=sample_data["admin_id"]
        )

        assert user.google_classroom_access is True
