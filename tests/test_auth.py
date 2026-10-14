from sqlalchemy import select

from app import db
from app.models import User


def test_login_accepts_email_or_carnet(app, sample_data, csrf_token):
    client = app.test_client()
    token = csrf_token(client)

    for identifier in ("alumno@alumno.uspg.edu.gt", "2600001"):
        response = client.post(
            "/",
            data={
                "csrf_token": token,
                "identifier": identifier,
                "password": "Password123!",
            },
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/panel")
        client.post("/salir", data={"csrf_token": token})


def test_login_rejects_invalid_password(app, sample_data, csrf_token):
    client = app.test_client()
    response = client.post(
        "/",
        data={
            "csrf_token": csrf_token(client),
            "identifier": "alumno@alumno.uspg.edu.gt",
            "password": "incorrecta",
        },
    )

    assert response.status_code == 200
    assert "Correo o contraseña incorrectos." in response.text


def test_logout_requires_authentication_and_ends_session(
    app, sample_data, login_as, csrf_token
):
    client = app.test_client()
    token = csrf_token(client)
    login_as(client, sample_data["student_id"])

    response = client.post("/salir", data={"csrf_token": token})

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert client.get("/alumno").status_code == 302


def test_student_registration_and_csrf(app, csrf_token):
    client = app.test_client()
    response = client.post(
        "/registro",
        data={
            "csrf_token": csrf_token(client),
            "name": "Nueva alumna",
            "email": "nueva@alumno.uspg.edu.gt",
            "carnet": "2600042",
            "password": "Password123!",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        user = db.session.scalar(
            select(User).where(User.email == "nueva@alumno.uspg.edu.gt")
        )
        assert user is not None
        assert user.role == "alumno"
        assert user.carnet == "2600042"
        assert user.check_password("Password123!")

    assert client.post("/registro", data={"email": "sin-token@alumno.uspg.edu.gt"}).status_code == 400


def test_authenticated_account_with_wrong_domain_is_rejected(app, login_as):
    client = app.test_client()
    with app.app_context():
        user = User(
            name="Cuenta incorrecta",
            email="rol-equivocado@alumno.uspg.edu.gt",
            role="admin",
        )
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    login_as(client, user_id)

    assert client.get("/admin").status_code == 403
