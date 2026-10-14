from email_validator import EmailNotValidError, validate_email
from sqlalchemy.exc import IntegrityError

from app.models import ExpoAttendance
from app.repositories import ExpoRepository


class ExpoService:
    CATEGORIES = {
        "estudiante": "Estudiante",
        "catedratico": "Catedrático",
        "publico": "Público general",
    }

    def __init__(self, repository=None):
        self.repository = repository or ExpoRepository()

    def register(self, name, email, category, participation, opinion, consent):
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
