from sqlalchemy import select

from app.backup import create_backup
from app.extensions import db
from app.models import User


def reset_demo_data(backup_destination, configured_admin_email=""):
    """Back up and remove all data except one administrator account."""
    configured_admin_email = configured_admin_email.strip().lower()
    administrators = list(
        db.session.scalars(
            select(User).where(User.role == "admin").order_by(User.id)
        )
    )
    administrator = next(
        (
            user
            for user in administrators
            if configured_admin_email and user.email == configured_admin_email
        ),
        None,
    )
    if administrator is None and len(administrators) == 1:
        administrator = administrators[0]
    if administrator is None:
        raise ValueError(
            "No se encontró un administrador único que se pueda conservar."
        )

    table_count, row_count = create_backup(backup_destination)
    try:
        for table in reversed(db.metadata.sorted_tables):
            statement = table.delete()
            if table.name == User.__tablename__:
                statement = statement.where(table.c.id != administrator.id)
            db.session.execute(statement)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return administrator, table_count, row_count
