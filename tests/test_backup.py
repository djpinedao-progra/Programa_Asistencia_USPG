from sqlalchemy import func, select

from app import db
from app.backup import create_backup, restore_backup
from app.models import User


def test_backup_restore_round_trip(app, sample_data, tmp_path):
    backup_file = tmp_path / "asistencia.gz"
    with app.app_context():
        table_count, row_count = create_backup(backup_file)
        assert table_count > 0
        assert row_count > 0

        db.session.execute(db.delete(User))
        db.session.commit()
        assert db.session.scalar(select(func.count()).select_from(User)) == 0

        restored_tables, restored_rows = restore_backup(backup_file)
        assert restored_tables == table_count
        assert restored_rows == row_count
        assert db.session.scalar(select(func.count()).select_from(User)) == 5


def test_reset_demo_keeps_only_configured_admin(
    app, sample_data, tmp_path, monkeypatch
):
    backup_file = tmp_path / "before-demo-reset.gz"
    monkeypatch.setenv("ADMIN_EMAIL", "admin@administrador.uspg.edu.gt")

    result = app.test_cli_runner().invoke(
        args=["reset-demo", "--yes", "--backup", str(backup_file)]
    )

    assert result.exit_code == 0, result.output
    assert backup_file.exists()
    with app.app_context():
        users = list(db.session.scalars(select(User)))
        assert len(users) == 1
        assert users[0].email == "admin@administrador.uspg.edu.gt"
        assert users[0].role == "admin"
        assert users[0].check_password("Password123!")
        for table in db.metadata.sorted_tables:
            if table.name != User.__tablename__:
                assert db.session.scalar(
                    select(func.count()).select_from(table)
                ) == 0
