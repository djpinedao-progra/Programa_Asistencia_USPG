from app.controllers import main
from app.controllers.decorators import roles_required
from app.security import csrf_token


def _csv_safe(value):
    value = str(value or "")
    if value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + value
    return value


__all__ = ["main", "roles_required", "csrf_token", "_csv_safe"]
