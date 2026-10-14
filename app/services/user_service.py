import re

from sqlalchemy.exc import IntegrityError

from app.models import User
from app.repositories import UserRepository
from app.services.audit_service import AuditService


class UserService:
    ALLOWED_ROLES = {"admin", "docente", "alumno"}
    EMAIL_ROLES = {
        "alumno.uspg.edu.gt": "alumno",
        "catedratico.uspg.edu.gt": "docente",
        "administrador.uspg.edu.gt": "admin",
        "uspg.edu": "admin",
    }
    MIN_PASSWORD_LENGTH = 8

    @classmethod
    def email_role(cls, email):
        email = email.strip().lower()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+", email):
            return None
        return cls.EMAIL_ROLES.get(email.split("@")[1])

    @classmethod
    def validate_email_role(cls, email, role):
        if cls.email_role(email) != role:
            raise ValueError("El dominio del correo universitario no corresponde al rol seleccionado.")

    @classmethod
    def validate_password(cls, password):
        if not password or len(password) < cls.MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"La contraseña debe tener al menos {cls.MIN_PASSWORD_LENGTH} caracteres."
            )

    def __init__(self, users=None):
        self.users = users or UserRepository()

    def list_all(self):
        return self.users.list_all()

    def list_by_role(self, role):
        return self.users.list_by_role(role)

    def find_by_id(self, user_id):
        return self.users.find_by_id(user_id)

    def find_by_login_identifier(self, identifier):
        return self.users.find_by_login_identifier(identifier)

    def create_user(self, name, email, password, role, carnet="", actor_id=None):
        name, email = name.strip(), email.strip().lower()
        carnet = carnet.strip()
        if not name or "@" not in email:
            raise ValueError("Completa todos los datos obligatorios.")
        self.validate_email_role(email, role)
        self.validate_password(password)
        if role not in self.ALLOWED_ROLES:
            raise ValueError("El rol seleccionado no es válido.")
        if role == "alumno" and not re.fullmatch(r"\d{7}", carnet):
            raise ValueError("El carnet debe tener exactamente 7 dígitos, por ejemplo *******.")
        if self.users.find_by_email(email):
            raise ValueError("Ya existe una cuenta con ese correo.")
        if carnet and self.users.find_by_carnet(carnet):
            raise ValueError("Ya existe una cuenta con ese carnet.")
        user = User(name=name, email=email, carnet=carnet or None, role=role)
        user.set_password(password)
        try:
            self.users.stage(user)
            AuditService.record(
                actor_id or user.id, "user_created", "user", user.id,
                {"role": role},
            )
            return self.users.add(user)
        except IntegrityError as error:
            self.users.rollback()
            raise ValueError("Ya existe una cuenta con ese correo o carnet.") from error

    def register_student(self, name, email, carnet, password):
        return self.create_user(name, email, password, "alumno", carnet)

    def assign_student_carnet(self, user_id, carnet, actor_id=None):
        carnet = carnet.strip()
        if not re.fullmatch(r"\d{7}", carnet):
            raise ValueError("El carnet debe tener exactamente 7 dígitos.")
        user = self.users.find_by_id(user_id)
        if not user or user.role != "alumno":
            raise ValueError("Solo se puede asignar carnet a una cuenta de alumno.")
        existing_user = self.users.find_by_carnet(carnet)
        if existing_user and existing_user.id != user.id:
            raise ValueError("Ese carnet ya pertenece a otra cuenta.")
        previous_carnet = user.carnet
        user.carnet = carnet
        if previous_carnet != carnet:
            AuditService.record(
                actor_id, "carnet_updated", "user", user.id,
                {"previous_carnet": previous_carnet, "carnet": carnet},
            )
        try:
            return self.users.save(user)
        except IntegrityError as error:
            self.users.rollback()
            raise ValueError("Ese carnet ya pertenece a otra cuenta.") from error



    def update_profile(self, user_id, name, email, carnet="", actor_id=None):
        user = self.users.find_by_id(user_id)
        name, email, carnet = name.strip(), email.strip().lower(), carnet.strip()
        if not user or user.role not in {"alumno", "docente"}:
            raise ValueError("No se encontró el perfil académico.")
        if not name or "@" not in email:
            raise ValueError("Indica un nombre y correo institucional válidos.")
        self.validate_email_role(email, user.role)
        existing_email = self.users.find_by_email(email)
        if existing_email and existing_email.id != user.id:
            raise ValueError("Ese correo ya pertenece a otra cuenta.")
        if user.role == "alumno" and carnet and not re.fullmatch(r"\d{7}", carnet):
            raise ValueError("El carnet debe contener exactamente 7 dígitos.")
        if user.role == "alumno" and carnet:
            existing_carnet = self.users.find_by_carnet(carnet)
            if existing_carnet and existing_carnet.id != user.id:
                raise ValueError("Ese carnet ya pertenece a otra cuenta.")
        changed_fields = [
            field for field, old, new in (
                ("name", user.name, name),
                ("email", user.email, email),
                ("carnet", user.carnet, carnet or None),
            ) if old != new and (field != "carnet" or user.role == "alumno")
        ]
        user.name = name
        user.email = email
        if user.role == "alumno":
            user.carnet = carnet or None
        if changed_fields:
            AuditService.record(
                actor_id, "profile_updated", "user", user.id,
                {"changed_fields": changed_fields},
            )
        try:
            return self.users.save(user)
        except IntegrityError as error:
            self.users.rollback()
            raise ValueError("El correo o carnet ya pertenece a otra cuenta.") from error

    def change_password(self, user_id, current_password, new_password, confirmation):
        user = self.users.find_by_id(user_id)
        if not user or not user.check_password(current_password):
            raise ValueError("La contraseña actual no es correcta.")
        self._save_new_password(
            user, new_password, confirmation, user.id, "password_changed"
        )

    def admin_reset_password(self, user_id, new_password, confirmation, actor_id=None):
        user = self.users.find_by_id(user_id)
        if not user or user.role not in {"alumno", "docente"}:
            raise ValueError("No se encontró la cuenta académica.")
        self._save_new_password(
            user, new_password, confirmation, actor_id, "password_reset"
        )

    def _save_new_password(self, user, new_password, confirmation, actor_id, action):
        self.validate_password(new_password)
        if new_password != confirmation:
            raise ValueError("La confirmación de contraseña no coincide.")
        user.set_password(new_password)
        pending = self.users.find_password_replacement(user.id)
        if pending:
            self.users.delete_password_replacement(pending)
        AuditService.record(actor_id, action, "user", user.id)
        self.users.commit_changes()
