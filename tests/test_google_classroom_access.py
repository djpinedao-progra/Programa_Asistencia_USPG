from app import db
from app.models import User
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
        tester = User(
            name="Analista de pruebas",
            email="analista@alumno.uspg.edu.gt",
            carnet="9900001",
            role="alumno",
            google_classroom_access=True,
        )
        tester.set_password("Password123!")
        db.session.add(tester)
        db.session.commit()
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
