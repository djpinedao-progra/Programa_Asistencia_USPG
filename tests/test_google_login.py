"""Pruebas del acceso con la cuenta institucional de Google."""


def _enable_google_login(app):
    app.config.update(
        GOOGLE_LOGIN_ENABLED=True,
        GOOGLE_LOGIN_AUTO_REDIRECT=True,
        GOOGLE_CLIENT_ID="client-id",
        GOOGLE_CLIENT_SECRET="client-secret",
        GOOGLE_LOGIN_REDIRECT_URI="https://staging.example/auth/google/callback",
    )


def test_login_sends_people_to_google_when_direct_access_is_enabled(app):
    _enable_google_login(app)

    response = app.test_client().get("/")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/google?")


def test_google_callback_opens_the_registered_account(app, sample_data, monkeypatch):
    _enable_google_login(app)
    monkeypatch.setattr(
        "app.controllers.auth_controller.GoogleLoginService.verified_email_from_code",
        lambda *_args: "alumno@alumno.uspg.edu.gt",
    )
    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["google_login_state"] = "safe-state"
        user_session["google_login_code_verifier"] = "safe-verifier"

    response = client.get("/auth/google/callback?state=safe-state&code=one-code")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/panel")
    with client.session_transaction() as user_session:
        assert user_session["_user_id"] == str(sample_data["student_id"])


def test_google_callback_rejects_a_state_that_does_not_match(app):
    _enable_google_login(app)
    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["google_login_state"] = "safe-state"
        user_session["google_login_code_verifier"] = "safe-verifier"

    response = client.get("/auth/google/callback?state=another-state&code=one-code")

    assert response.status_code == 400


def test_google_login_refuses_an_account_that_is_not_registered(
    app, sample_data, monkeypatch
):
    _enable_google_login(app)
    monkeypatch.setattr(
        "app.controllers.auth_controller.GoogleLoginService.verified_email_from_code",
        lambda *_args: "nadie@alumno.uspg.edu.gt",
    )
    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["google_login_state"] = "safe-state"
        user_session["google_login_code_verifier"] = "safe-verifier"

    response = client.get("/auth/google/callback?state=safe-state&code=one-code")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/?acceso=local")
