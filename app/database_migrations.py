"""Cambios pequeños para bases de datos creadas antes de nuevas funciones."""

from sqlalchemy import inspect, text

from app.extensions import db


def ensure_google_classroom_access_column():
    """Agrega el permiso de pruebas a instalaciones que ya tenían la tabla users."""
    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "google_classroom_access" in columns:
        return
    with db.engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE users ADD COLUMN google_classroom_access "
                "BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
