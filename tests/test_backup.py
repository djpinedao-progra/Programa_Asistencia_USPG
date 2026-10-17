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
