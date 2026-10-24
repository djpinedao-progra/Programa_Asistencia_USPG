import os
from pathlib import Path

import click
from sqlalchemy import inspect, select, text

from app.extensions import db


def register_commands(app):
    @app.cli.command("init-db")
    def init_db_command():
        """Create the database tables."""
        with app.app_context():
            db.create_all()
        click.echo("Tablas de asistencia creadas.")

    @app.cli.command("migrate-expo")
    def migrate_expo_command():
        """Add the public Expo table without changing existing attendance."""
        from app.models import ExpoAttendance

        ExpoAttendance.__table__.create(db.engine, checkfirst=True)
        click.echo("Registro público de Expo San Pablo listo.")

    @app.cli.command("migrate-carnet")
    def migrate_carnet_command():
        """Add the optional carnet column for existing user records."""
        inspector = inspect(db.engine)
        if "carnet" not in {
            column["name"] for column in inspector.get_columns("users")
        }:
            with db.engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE users ADD COLUMN carnet VARCHAR(20)")
                )
        inspector = inspect(db.engine)
        indexes = {index["name"] for index in inspector.get_indexes("users")}
        if "ix_users_carnet" not in indexes:
            with db.engine.begin() as connection:
                connection.execute(
                    text("CREATE UNIQUE INDEX ix_users_carnet ON users (carnet)")
                )
        click.echo(
            "Columna carnet lista. Los alumnos existentes pueden completar su "
            "carnet con el administrador."
        )

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
        from app.services.attendance_service import AttendanceService

        AttendanceService(
            auto_close_grace_minutes=app.config[
                "ATTENDANCE_CLOSE_GRACE_MINUTES"
            ],
            timezone_name=app.config["APP_TIMEZONE"],
        ).close_expired_sessions()
        click.echo(
            "Herramientas docentes listas; los datos existentes se conservaron."
        )

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
            f"Respaldo creado: {destination} ({row_count} filas en "
            f"{table_count} tablas)."
        )

    @app.cli.command("restore-db")
    @click.argument(
        "source", type=click.Path(path_type=Path, exists=True, dir_okay=False)
    )
    @click.option(
        "--yes", is_flag=True, help="Confirma sin mostrar el diálogo interactivo."
    )
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
            f"Restauración completada: {row_count} filas en "
            f"{table_count} tablas."
        )

    @app.cli.command("reset-demo")
    @click.option(
        "--backup",
        "backup_destination",
        required=True,
        type=click.Path(path_type=Path, dir_okay=False),
        help="Ruta obligatoria para respaldar los datos antes de limpiar.",
    )
    @click.option(
        "--yes", is_flag=True, help="Confirma sin mostrar el diálogo interactivo."
    )
    def reset_demo_command(backup_destination, yes):
        """Remove all data except the configured administrator account."""
        from app.backup import create_backup
        from app.models import User

        if not yes:
            click.confirm(
                "Se eliminarán todos los datos excepto el administrador. "
                "¿Continuar?",
                abort=True,
            )

        configured_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        administrators = list(
            db.session.scalars(
                select(User).where(User.role == "admin").order_by(User.id)
            )
        )
        administrator = next(
            (
                user
                for user in administrators
                if configured_email and user.email == configured_email
            ),
            None,
        )
        if administrator is None and len(administrators) == 1:
            administrator = administrators[0]
        if administrator is None:
            raise click.ClickException(
                "No se encontró un administrador único que se pueda conservar."
            )

        try:
            table_count, row_count = create_backup(backup_destination)
            for table in reversed(db.metadata.sorted_tables):
                statement = table.delete()
                if table.name == User.__tablename__:
                    statement = statement.where(table.c.id != administrator.id)
                db.session.execute(statement)
            db.session.commit()
        except (OSError, ValueError) as error:
            db.session.rollback()
            raise click.ClickException(str(error)) from error
        except Exception:
            db.session.rollback()
            raise

        click.echo(
            f"Demo limpia. Se conservó el administrador {administrator.email}. "
            f"Respaldo: {backup_destination} ({row_count} filas en "
            f"{table_count} tablas)."
        )

    @app.cli.command("seed-admin")
    def seed_admin_command():
        """Create the first administrator using ADMIN_EMAIL and ADMIN_PASSWORD."""
        from app.models import User
        from app.services import UserService

        email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("ADMIN_PASSWORD", "")
        if not email or not password:
            raise click.ClickException("Configura ADMIN_EMAIL y ADMIN_PASSWORD.")
        try:
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
