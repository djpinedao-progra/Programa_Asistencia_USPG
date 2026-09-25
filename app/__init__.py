import os
from datetime import datetime, timezone

import click
from flask import Flask, abort, request, session
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, select, text
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message = "Inicia sesión para continuar."
login_manager.login_message_category = "warning"


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "local-development-key-change-me"),
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL", "sqlite:///asistencia.db"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        QR_SESSION_MINUTES=15,
        APP_BASE_URL=os.getenv("APP_BASE_URL", "").rstrip("/"),
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)

    from app import models
    from app.routes import main

    app.register_blueprint(main)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    @app.before_request
    def protect_mutations():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            expected = session.get("csrf_token", "")
            supplied = request.headers.get("X-CSRFToken") or request.form.get(
                "csrf_token", ""
            )
            import hmac

            if not expected or not hmac.compare_digest(expected, supplied):
                abort(400, description="Token de seguridad inválido.")

    @app.context_processor
    def inject_template_helpers():
        from app.routes import csrf_token

        return {"csrf_token": csrf_token, "current_year": datetime.now(timezone.utc).year}

    @app.cli.command("init-db")
    def init_db_command():
        """Create the database tables."""
        with app.app_context():
            db.create_all()
        click.echo("Tablas de asistencia creadas.")

    @app.cli.command("migrate-carnet")
    def migrate_carnet_command():
        """Add the optional carnet column for existing user records."""
        inspector = inspect(db.engine)
        if "carnet" not in {column["name"] for column in inspector.get_columns("users")}:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN carnet VARCHAR(20)"))
        inspector = inspect(db.engine)
        indexes = {index["name"] for index in inspector.get_indexes("users")}
        if "ix_users_carnet" not in indexes:
            with db.engine.begin() as connection:
                connection.execute(
                    text("CREATE UNIQUE INDEX ix_users_carnet ON users (carnet)")
                )
        click.echo("Columna carnet lista. Los alumnos existentes pueden completar su carnet con el administrador.")

    @app.cli.command("seed-admin")
    def seed_admin_command():
        """Create the first administrator using ADMIN_EMAIL and ADMIN_PASSWORD."""
        from app.models import User

        email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("ADMIN_PASSWORD", "")
        if not email or not password:
            raise click.ClickException(
                "Configura ADMIN_EMAIL y una ADMIN_PASSWORD no vacía."
            )
        if db.session.scalar(select(User).where(User.email == email)):
            raise click.ClickException("Ya existe una cuenta con ese correo.")
        admin = User(name="Administrador", email=email, role="admin")
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Administrador creado: {email}")

    return app