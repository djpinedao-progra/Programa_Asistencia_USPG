"""Pruebas del acceso con la cuenta institucional de Google."""

from app.services.google_login_service import GoogleLoginService


def _enable_google_login(app):
    app.config.update(
        GOOGLE_LOGIN_ENABLED=True,
        GOOGLE_LOGIN_AUTO_REDIRECT=True,
        GOOGLE_CLIENT_ID="client-id",
        GOOGLE_CLIENT_SECRET="client-secret",
        GOOGLE_LOGIN_REDIRECT_URI="https://staging.example/auth/google/callback",
    )


def test_login_keeps_the_choice_screen_when_google_direct_access_is_enabled(app):
    _enable_google_login(app)

    response = app.test_client().get("/")

    assert response.status_code == 200


def test_login_can_send_people_to_google_when_requested(app):
    _enable_google_login(app)

    response = app.test_client().get("/?acceso=google")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/google?")


def test_google_login_asks_only_for_identity_permissions(app, monkeypatch):
    _enable_google_login(app)
    received = {}

    class FakeFlow:
        code_verifier = "safe-verifier"

        def authorization_url(self, **kwargs):
            received.update(kwargs)
            return "https://accounts.google.test/authorize", "safe-state"

    monkeypatch.setattr(
        "app.services.google_login_service.Flow.from_client_config",
        lambda *_args, **_kwargs: FakeFlow(),
    )

    url, state, verifier = GoogleLoginService().authorization_url()

    assert url == "https://accounts.google.test/authorize"
    assert state == "safe-state"
    assert verifier == "safe-verifier"
    assert received == {"access_type": "online", "prompt": "select_account"}


def test_google_login_uses_the_scope_names_returned_by_google(app, monkeypatch):
    _enable_google_login(app)
    received = {}

    class FakeFlow:
        code_verifier = "safe-verifier"

        def authorization_url(self, **_kwargs):
            return "https://accounts.google.test/authorize", "safe-state"

    def fake_from_client_config(_config, **kwargs):
        received.update(kwargs)
        return FakeFlow()

    monkeypatch.setattr(
        "app.services.google_login_service.Flow.from_client_config",
        fake_from_client_config,
    )

    GoogleLoginService().authorization_url()

    assert received["scopes"] == (
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    )


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
    assert "acceso=local" in response.headers["Location"]
    assert "error_google=Tu+cuenta+de+Google" in response.headers["Location"]


def test_google_login_checks_the_verified_email_with_google(app, monkeypatch):
    _enable_google_login(app)

    class FakeFlow:
        credentials = object()

        def fetch_token(self, authorization_response):
            assert "code=one-code" in authorization_response

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "email": "Alumno@Alumno.USPG.edu.gt",
                "email_verified": True,
            }

    class FakeGoogleSession:
        def get(self, url, timeout):
            assert url == "https://openidconnect.googleapis.com/v1/userinfo"
            assert timeout == 10
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.google_login_service.Flow.from_client_config",
        lambda *_args, **_kwargs: FakeFlow(),
    )
    monkeypatch.setattr(
        "app.services.google_login_service.AuthorizedSession",
        lambda _credentials: FakeGoogleSession(),
    )

    assert GoogleLoginService().verified_email_from_code(
        "https://staging.example/auth/google/callback?code=one-code",
        "safe-state",
        "safe-verifier",
    ) == "alumno@alumno.uspg.edu.gt"


def test_google_callback_shows_a_safe_message_for_an_unexpected_error(
    app, sample_data, monkeypatch
):
    _enable_google_login(app)

    def fail_to_read_google_response(*_args):
        raise RuntimeError("technical detail")

    monkeypatch.setattr(
        "app.controllers.auth_controller.GoogleLoginService.verified_email_from_code",
        fail_to_read_google_response,
    )
    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["google_login_state"] = "safe-state"
        user_session["google_login_code_verifier"] = "safe-verifier"

    response = client.get("/auth/google/callback?state=safe-state&code=one-code")

    assert response.status_code == 302
    assert "error_google=No+fue+posible+terminar" in response.headers["Location"]
    assert "RuntimeError" in response.headers["Location"]
