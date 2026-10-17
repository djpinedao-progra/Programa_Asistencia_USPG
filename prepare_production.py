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
            db.select(User.id).where(User.role == "admin")
        )
        if existing_admin:
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
