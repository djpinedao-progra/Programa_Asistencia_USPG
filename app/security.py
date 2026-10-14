import hmac
import secrets

from flask import abort, request, session
from flask_login import current_user, logout_user


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def protect_mutations():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        expected = session.get("csrf_token", "")
        supplied = request.headers.get("X-CSRFToken") or request.form.get(
            "csrf_token", ""
        )
        if not expected or not hmac.compare_digest(expected, supplied):
            abort(400, description="Token de seguridad inválido.")


def enforce_account_domain():
    if current_user.is_authenticated:
        from app.services import UserService

        if UserService.email_role(current_user.email) != current_user.role:
            logout_user()
            abort(403, description="El correo institucional no corresponde al rol de la cuenta.")


def register_security_hooks(app):
    app.before_request(enforce_account_domain)
    app.before_request(protect_mutations)

    @app.context_processor
    def inject_template_helpers():
        from datetime import datetime, timezone

        return {
            "csrf_token": csrf_token,
            "current_year": datetime.now(timezone.utc).year,
        }
