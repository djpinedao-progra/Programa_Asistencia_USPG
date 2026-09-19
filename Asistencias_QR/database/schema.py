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
            CREATE TABLE IF NOT EXISTS cursos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                seccion TEXT NOT NULL DEFAULT '',
                docente TEXT NOT NULL DEFAULT '',
                estado TEXT NOT NULL DEFAULT 'activo'
                    CHECK (estado IN ('activo', 'inactivo'))
            );
            CREATE TABLE IF NOT EXISTS sesiones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                curso TEXT NOT NULL,
                curso_id INTEGER,
                fecha_hora TEXT NOT NULL,
                token_qr TEXT NOT NULL UNIQUE,
                FOREIGN KEY (curso_id) REFERENCES cursos(id)
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
        columnas_sesiones = {
            columna["name"] for columna in connection.execute("PRAGMA table_info(sesiones)")
        }
        if "curso_id" not in columnas_sesiones:
            connection.execute(
                "ALTER TABLE sesiones ADD COLUMN curso_id INTEGER REFERENCES cursos(id)"
            )
