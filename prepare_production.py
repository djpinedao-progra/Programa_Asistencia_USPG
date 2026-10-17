"""Initialize an external database without creating demo accounts."""
import os

from app import db
from app.models import User
from app.services import UserService


def prepare_database(application):
    """Create the schema and the first admin; safe to run on every boot."""
    with application.app_context():
        db.create_all()
        existing_admin = db.session.scalar(
            db.select(User).where(User.role == "admin").order_by(User.id)
        )
        if existing_admin:
            if os.getenv("RESET_ADMIN_CREDENTIALS", "").strip().lower() in {
                "1",
                "true",
                "yes",
                "si",
                "sí",
            }:
                email = os.getenv("ADMIN_EMAIL", "").strip().lower()
                password = os.getenv("ADMIN_PASSWORD", "")
                if not email or not password:
                    raise RuntimeError(
                        "Configura ADMIN_EMAIL y ADMIN_PASSWORD en Render."
                    )
                UserService.validate_email_role(email, "admin")
                UserService.validate_password(password)
                conflicting_user = db.session.scalar(
                    db.select(User).where(
                        User.email == email,
                        User.id != existing_admin.id,
                    )
                )
                if conflicting_user:
                    raise RuntimeError(
                        "ADMIN_EMAIL ya pertenece a otra cuenta del sistema."
                    )
                existing_admin.email = email
                existing_admin.set_password(password)
                db.session.commit()
                print("Credenciales de la cuenta administradora restablecidas.")
                return True
            print("Base de datos lista; ya existe una cuenta administradora.")
            return False

        email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("ADMIN_PASSWORD", "")
        if not email or not password:
            raise RuntimeError(
                "Configura ADMIN_EMAIL y ADMIN_PASSWORD en Render."
            )
        UserService().create_user("Administrador", email, password, "admin")
        print("Cuenta administradora creada. No se crearon usuarios demo.")
        return True


if __name__ == "__main__":
    from run import app

    prepare_database(app)
