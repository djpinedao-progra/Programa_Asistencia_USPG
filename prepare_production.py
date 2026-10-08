"""Prepare a fresh production database: create tables and the first administrator, no demo data."""
import os

from app import db
from app.models import User
from app.services import UserService
from run import app

with app.app_context():
    db.create_all()
    if not db.session.scalar(db.select(User.id).where(User.role == "admin")):
        email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("ADMIN_PASSWORD", "")
        UserService().create_user("Administrador", email, password, "admin")
        db.session.commit()
        print("Cuenta administradora creada. No se crearon cuentas de prueba.")
