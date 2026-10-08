import base64
import gzip
import json
import os
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from app import db


BACKUP_FORMAT = "uspg-attendance-backup"
BACKUP_VERSION = 1


def _json_default(value):
    if isinstance(value, datetime):
        return {"__type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__type__": "date", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"__type__": "decimal", "value": str(value)}
    if isinstance(value, bytes):
        return {"__type__": "bytes", "value": base64.b64encode(value).decode("ascii")}
    raise TypeError(f"No se puede serializar el tipo {type(value).__name__}.")


def _json_object_hook(value):
    value_type = value.get("__type__")
    raw_value = value.get("value")
    if value_type == "datetime":
        return datetime.fromisoformat(raw_value)
    if value_type == "date":
        return date.fromisoformat(raw_value)
    if value_type == "decimal":
        return Decimal(raw_value)
    if value_type == "bytes":
        return base64.b64decode(raw_value, validate=True)
    return value


def create_backup(destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tables = db.metadata.sorted_tables
    payload = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_dialect": db.engine.dialect.name,
        "tables": {},
    }
    row_count = 0
    with db.engine.connect() as connection:
        with connection.begin():
            for table in tables:
                rows = [dict(row) for row in connection.execute(table.select()).mappings()]
                payload["tables"][table.name] = {
                    "columns": [column.name for column in table.columns],
                    "rows": rows,
                }
                row_count += len(rows)

    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, prefix=f".{destination.name}.", delete=False
        ) as temp_file:
            temp_name = temp_file.name
        with gzip.open(temp_name, "wt", encoding="utf-8") as archive:
            json.dump(payload, archive, default=_json_default, separators=(",", ":"))
        if os.name != "nt":
            os.chmod(temp_name, 0o600)
        os.replace(temp_name, destination)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return len(tables), row_count


def restore_backup(source):
    source = Path(source)
    try:
        with gzip.open(source, "rt", encoding="utf-8") as archive:
            payload = json.load(archive, object_hook=_json_object_hook)
    except (EOFError, gzip.BadGzipFile, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("El archivo no es un respaldo válido.") from error

    if not isinstance(payload, dict):
        raise ValueError("El archivo no es un respaldo válido.")
    if payload.get("format") != BACKUP_FORMAT or payload.get("version") != BACKUP_VERSION:
        raise ValueError("El formato o la versión del respaldo no son compatibles.")
    archived_tables = payload.get("tables")
    expected_tables = {table.name: table for table in db.metadata.sorted_tables}
    if not isinstance(archived_tables, dict) or set(archived_tables) != set(expected_tables):
        raise ValueError("El esquema del respaldo no coincide con esta versión del programa.")

    row_count = 0
    for table_name, table in expected_tables.items():
        table_data = archived_tables[table_name]
        if not isinstance(table_data, dict):
            raise ValueError(f"La definición de la tabla {table_name} no coincide.")
        columns = [column.name for column in table.columns]
        if table_data.get("columns") != columns or not isinstance(table_data.get("rows"), list):
            raise ValueError(f"La definición de la tabla {table_name} no coincide.")
        for row in table_data["rows"]:
            if not isinstance(row, dict) or set(row) != set(columns):
                raise ValueError(f"Hay una fila incompatible en la tabla {table_name}.")
        row_count += len(table_data["rows"])

    tables = list(db.metadata.sorted_tables)
    with db.engine.begin() as connection:
        for table in reversed(tables):
            connection.execute(table.delete())
        for table in tables:
            rows = archived_tables[table.name]["rows"]
            for offset in range(0, len(rows), 500):
                connection.execute(table.insert(), rows[offset : offset + 500])
    return len(tables), row_count
