from .conexion import get_connection


def init_db():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS estudiantes (
                carnet TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                correo TEXT NOT NULL,
                carrera TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'activo'
            );
            CREATE TABLE IF NOT EXISTS sesiones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                curso TEXT NOT NULL,
                fecha_hora TEXT NOT NULL,
                token_qr TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS asistencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                carnet TEXT NOT NULL,
                sesion_id INTEGER NOT NULL,
                fecha_hora TEXT NOT NULL,
                FOREIGN KEY (carnet) REFERENCES estudiantes(carnet),
                FOREIGN KEY (sesion_id) REFERENCES sesiones(id),
                UNIQUE (carnet, sesion_id)
            );
            """
        )