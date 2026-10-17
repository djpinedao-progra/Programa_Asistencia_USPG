from sqlalchemy import text

from app.extensions import db


class BackupRepository:
    def read_database(self):
        return db.engine.dialect.name, {
            table.name: {
                "columns": [column.name for column in table.columns],
                "rows": [
                    {col.name: value for col, value in zip(table.columns, row)}
                    for row in db.session.execute(table.select()).all()
                ],
            }
            for table in db.metadata.sorted_tables
        }

    def table_columns(self):
        return {
            table.name: [column.name for column in table.columns]
            for table in db.metadata.sorted_tables
        }

    def replace_database(self, archived_tables):
        for table in db.metadata.sorted_tables:
            db.session.execute(text(f"DELETE FROM {table.name}"))
            rows = archived_tables.get(table.name, {}).get("rows", [])
            if rows:
                columns = [column.name for column in table.columns]
                db.session.execute(
                    table.insert(),
                    [{key: row.get(key) for key in columns} for row in rows],
                )
        db.session.commit()
