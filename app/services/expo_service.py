from email_validator import EmailNotValidError, validate_email
from sqlalchemy.exc import IntegrityError

from app.models import ExpoAttendance
from app.repositories import ExpoRepository
from app.services.audit_service import AuditService


class ExpoService:
    ACCESS_SETTING = "expo_registration_enabled"
    CATEGORIES = {
        "estudiante": "Estudiante",
        "catedratico": "Catedrático",
        "publico": "Público general",
    }

    def __init__(self, repository=None):
        self.repository = repository or ExpoRepository()

    def count_by_category(self):
        return self.repository.count_by_category()

    def paginate(self, category=None, per_page=25):
        return self.repository.paginate(category, per_page=per_page)

    def list_filtered(self, category=None):
        return self.repository.list_filtered(category)

    def is_registration_enabled(self):
        setting = self.repository.get_setting(self.ACCESS_SETTING)
        return setting is None or setting.value == "true"

    def set_registration_enabled(self, enabled, actor_id=None):
        enabled = bool(enabled)
        self.repository.set_setting(
            self.ACCESS_SETTING, "true" if enabled else "false"
        )
        AuditService.record(
            actor_id,
            "expo_access_changed",
            "app_setting",
            details={"enabled": enabled},
        )
        self.repository.commit()
        return enabled

    def register(self, name, email, category, participation, opinion, consent):
        if not self.is_registration_enabled():
            raise ValueError("El registro de Expo San Pablo está deshabilitado.")
        name = name.strip()
        if not 2 <= len(name) <= 120:
            raise ValueError(
                "Escribe tu nombre completo (entre 2 y 120 caracteres)."
            )
        try:
            email = validate_email(
                email.strip(), check_deliverability=False
            ).normalized.casefold()
        except EmailNotValidError as error:
            raise ValueError(
                "Escribe un correo electrónico válido, personal o institucional."
            ) from error
        if len(email) > 254:
            raise ValueError("El correo es demasiado largo.")
        if category not in self.CATEGORIES:
            raise ValueError("Selecciona estudiante, catedrático o público general.")
        participation = participation.strip()
        opinion = opinion.strip()
        if not 1 <= len(participation) <= 500:
            raise ValueError("Describe tu participación (máximo 500 caracteres).")
        if len(opinion) > 2000:
            raise ValueError("Tu opinión debe tener como máximo 2000 caracteres.")
        if consent != "yes":
            raise ValueError("Autoriza el registro de tus datos para este evento.")
        if self.repository.find_by_email(email):
            return False
        try:
            self.repository.add(
                ExpoAttendance(
                    name=name,
                    email=email,
                    category=category,
                    participation=participation,
                    opinion=opinion,
                )
            )
        except IntegrityError:
            return False
        return True
