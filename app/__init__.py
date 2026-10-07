import os
import secrets
from pathlib import Path
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
    app_env = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
    env_secret = os.getenv("SECRET_KEY")
    database_url = os.getenv("DATABASE_URL", "sqlite:///luis_independiente.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config.from_mapping(
        SECRET_KEY=env_secret or secrets.token_urlsafe(48),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=app_env == "production",
        QR_SESSION_MINUTES=1,
        APP_BASE_URL=os.getenv("APP_BASE_URL", os.getenv("RENDER_EXTERNAL_URL", "")).rstrip("/"),
        APP_TIMEZONE=os.getenv("APP_TIMEZONE", "America/Guatemala"),
        APP_ENV=app_env,
    )
    if test_config:
        app.config.update(test_config)
    if app.config.get("APP_ENV") == "production":
        app.config["SESSION_COOKIE_SECURE"] = True
    if (
        app.config.get("APP_ENV") == "production"
        and not env_secret
        and not (test_config and test_config.get("SECRET_KEY"))
    ):
        raise RuntimeError(
            "SECRET_KEY es obligatoria cuando APP_ENV=production."
        )

    if app.config.get("APP_ENV") == "production" and not os.getenv("DATABASE_URL") and not test_config:
        raise RuntimeError("DATABASE_URL es obligatoria en producción.")
    db.init_app(app)
    login_manager.init_app(app)

    from app.time_utils import local_datetime

    app.add_template_filter(
        lambda value: local_datetime(value, app.config["APP_TIMEZONE"]),
        "localtime",
    )

    from app import models
    from app.routes import main

    app.register_blueprint(main)
    from app.expo import expo
    app.register_blueprint(expo)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    @app.before_request
    def enforce_account_domain():
        from flask_login import current_user, logout_user
        from app.services import UserService
        if current_user.is_authenticated and UserService.email_role(current_user.email) != current_user.role:
            logout_user()
            abort(403, description="El correo institucional no corresponde al rol de la cuenta.")

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

        return {
            "csrf_token": csrf_token,
            "current_year": datetime.now(timezone.utc).year,
        }

    @app.cli.command("init-db")
    def init_db_command():
        """Create the database tables."""
        with app.app_context():
            db.create_all()
        click.echo("Tablas de asistencia creadas.")

    @app.cli.command("migrate-expo")
    def migrate_expo_command():
        """Add the public Expo table without changing existing attendance."""
        models.ExpoAttendance.__table__.create(db.engine, checkfirst=True)
        click.echo("Registro público de Expo San Pablo listo.")

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

    @app.cli.command("migrate-teacher-tools")
    def migrate_teacher_tools_command():
        """Add course, attendance, enrollment, and notice fields for teacher tools."""
        additions = {
            "courses": {
                "schedule": "VARCHAR(180) NOT NULL DEFAULT ''",
                "location_type": "VARCHAR(20) NOT NULL DEFAULT 'presencial'",
                "classroom": "VARCHAR(100) NOT NULL DEFAULT ''",
                "is_active": "BOOLEAN NOT NULL DEFAULT 1",
            },
            "attendance_sessions": {"closed_at": "DATETIME"},
            "attendance": {
                "status": "VARCHAR(20) NOT NULL DEFAULT 'presente'",
                "source": "VARCHAR(20) NOT NULL DEFAULT 'qr'",
                "modified_by_id": "INTEGER",
                "modified_at": "DATETIME",
            },
        }
        inspector = inspect(db.engine)
        for table_name, columns in additions.items():
            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for column_name, column_definition in columns.items():
                if column_name not in existing_columns:
                    with db.engine.begin() as connection:
                        connection.execute(
                            text(
                                f"ALTER TABLE {table_name} ADD COLUMN "
                                f"{column_name} {column_definition}"
                            )
                        )
        db.create_all()
        with db.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE attendance_sessions "
                    "SET active = 0, closed_at = expires_at "
                    "WHERE closed_at IS NULL AND expires_at < :now"
                ),
                {"now": datetime.now(timezone.utc).replace(tzinfo=None)},
            )
        click.echo("Herramientas docentes listas; los datos existentes se conservaron.")

    @app.cli.command("migrate-audit-log")
    def migrate_audit_log_command():
        """Create the audit log table for existing installations."""
        db.create_all()
        click.echo("Tabla de auditoría lista.")

    @app.cli.command("backup-db")
    @click.argument("destination", type=click.Path(path_type=Path, dir_okay=False))
    def backup_db_command(destination):
        """Create a compressed, versioned backup of application data."""
        from app.backup import create_backup

        try:
            table_count, row_count = create_backup(destination)
        except (OSError, ValueError) as error:
            raise click.ClickException(str(error)) from error
        click.echo(
            f"Respaldo creado: {destination} ({row_count} filas en {table_count} tablas)."
        )

    @app.cli.command("restore-db")
    @click.argument("source", type=click.Path(path_type=Path, exists=True, dir_okay=False))
    @click.option("--yes", is_flag=True, help="Confirma sin mostrar el diálogo interactivo.")
    def restore_db_command(source, yes):
        """Replace application data using a compatible backup."""
        if not yes:
            click.confirm(
                "Esta operación reemplazará todos los datos actuales. ¿Continuar?",
                abort=True,
            )
        from app.backup import restore_backup

        try:
            table_count, row_count = restore_backup(source)
        except (OSError, ValueError) as error:
            raise click.ClickException(str(error)) from error
        click.echo(
            f"Restauración completada: {row_count} filas en {table_count} tablas."
        )

    @app.cli.command("seed-admin")
    def seed_admin_command():
        """Create the first administrator using ADMIN_EMAIL and ADMIN_PASSWORD."""
        from app.models import User

        email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("ADMIN_PASSWORD", "")
        if not email or not password:
            raise click.ClickException(
                "Configura ADMIN_EMAIL y ADMIN_PASSWORD."
            )
        try:
            from app.services import UserService
            UserService.validate_email_role(email, "admin")
            UserService.validate_password(password)
        except ValueError as error:
            raise click.ClickException(str(error)) from error
        if db.session.scalar(select(User).where(User.email == email)):
            raise click.ClickException("Ya existe una cuenta con ese correo.")
        admin = User(name="Administrador", email=email, role="admin")
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Administrador creado: {email}")

    return app
