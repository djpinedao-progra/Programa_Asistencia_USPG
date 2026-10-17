from flask import current_app

from app.services.recovery_service import (
    authenticate,
    request_replacement as _request_replacement,
    send_password,
    utc,
)


def request_replacement(email):
    return _request_replacement(email, current_app.logger)

__all__ = ["authenticate", "request_replacement", "send_password", "utc"]
