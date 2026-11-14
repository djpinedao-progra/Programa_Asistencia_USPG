"""Inicio de sesión con Google para cuentas institucionales ya registradas."""

from flask import current_app
from google.auth.transport.requests import AuthorizedSession
from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2.rfc6749.errors import OAuth2Error

from app.services.google_classroom_service import CLASSROOM_SCOPES

# Estos permisos solo identifican a la persona. No permiten leer ni cambiar Classroom.
# Se usan los nombres completos que Google devuelve al finalizar el inicio.
GOOGLE_LOGIN_SCOPES = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
)


class GoogleLoginConfigurationError(ValueError):
    """Se usa cuando aún faltan datos de Google Cloud."""


class GoogleLoginService:
    @staticmethod
    def enabled():
        return bool(current_app.config.get("GOOGLE_LOGIN_ENABLED"))

    @staticmethod
    def auto_redirect_enabled():
        return GoogleLoginService.enabled() and bool(
            current_app.config.get("GOOGLE_LOGIN_AUTO_REDIRECT")
        )

    @staticmethod
    def classroom_login_enabled():
        """Indica si el inicio con Google pide también lectura de Classroom."""
        return bool(current_app.config.get("GOOGLE_CLASSROOM_ENABLED"))

    @classmethod
    def requested_scopes(cls):
        """Usa los permisos de Classroom solo cuando la integración está activa."""
        return CLASSROOM_SCOPES if cls.classroom_login_enabled() else GOOGLE_LOGIN_SCOPES

    @staticmethod
    def _client_config():
        return {
            "web": {
                "client_id": current_app.config["GOOGLE_CLIENT_ID"],
                "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [current_app.config["GOOGLE_LOGIN_REDIRECT_URI"]],
            }
        }

    @classmethod
    def require_available(cls):
        if not cls.enabled():
            raise GoogleLoginConfigurationError("El inicio con Google está desactivado.")
        required = {
            "GOOGLE_CLIENT_ID": current_app.config.get("GOOGLE_CLIENT_ID"),
            "GOOGLE_CLIENT_SECRET": current_app.config.get("GOOGLE_CLIENT_SECRET"),
            "GOOGLE_LOGIN_REDIRECT_URI": current_app.config.get(
                "GOOGLE_LOGIN_REDIRECT_URI"
            ),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise GoogleLoginConfigurationError("Falta configurar: " + ", ".join(missing) + ".")

    def authorization_url(self):
        """Crea un enlace de un solo uso hacia la página segura de Google."""
        self.require_available()
        flow = Flow.from_client_config(
            self._client_config(), scopes=self.requested_scopes()
        )
        flow.redirect_uri = current_app.config["GOOGLE_LOGIN_REDIRECT_URI"]
        # Si Classroom está activo, Google entrega sus permisos de lectura en este mismo paso.
        url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt=(
                "select_account consent"
                if self.classroom_login_enabled()
                else "select_account"
            ),
        )
        return url, state, flow.code_verifier

    def verified_google_account_from_code(
        self, authorization_response, state, code_verifier
    ):
        """Recibe el código de Google y devuelve solo un correo ya comprobado."""
        self.require_available()
        if not authorization_response or not code_verifier:
            raise ValueError("Google no envió la información necesaria para iniciar sesión.")
        flow = Flow.from_client_config(
            self._client_config(), scopes=self.requested_scopes(), state=state
        )
        flow.redirect_uri = current_app.config["GOOGLE_LOGIN_REDIRECT_URI"]
        flow.code_verifier = code_verifier
        try:
            flow.fetch_token(authorization_response=authorization_response)
        except OAuth2Error as error:
            detail = error.description or error.error
            current_app.logger.warning(
                "Google rechazÃ³ el intercambio del permiso de inicio de sesiÃ³n: %s",
                detail,
            )
            raise ValueError(f"Google rechazÃ³ el acceso: {detail}.") from error
        try:
            google_session = AuthorizedSession(flow.credentials)
            response = google_session.get(
                "https://openidconnect.googleapis.com/v1/userinfo", timeout=10
            )
            response.raise_for_status()
            token = response.json()
        except Exception as error:
            current_app.logger.warning(
                "Google no permitió comprobar el token de inicio de sesión.",
                exc_info=True,
            )
            raise ValueError("No fue posible comprobar tu identidad con Google.") from error
        email = str(token.get("email", "")).strip().lower()
        email_verified = token.get("email_verified", token.get("verified_email", False))
        if not email or not email_verified:
            raise ValueError("Google no confirmó un correo electrónico válido.")
        domain = email.rsplit("@", 1)[-1]
        if domain not in {"uspg.edu", "uspg.edu.gt"} and not domain.endswith(
            ".uspg.edu.gt"
        ):
            raise ValueError("Usa una cuenta institucional de USPG para iniciar sesión.")
        return email, flow.credentials

    def verified_email_from_code(self, authorization_response, state, code_verifier):
        """Conserva la consulta de correo para código que aún la usa."""
        email, _credentials = self.verified_google_account_from_code(
            authorization_response, state, code_verifier
        )
        return email
