import sqlite3

from models.estudiante import Estudiante


class EstudianteService:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def registrar(self, datos):
        estudiante = Estudiante(
            carnet=self._required(datos, "carnet"),
            nombre=self._required(datos, "nombre"),
            correo=self._required(datos, "correo"),
            carrera=self._required(datos, "carrera"),
        )
        try:
            with self.connection_factory() as connection:
                connection.execute(
                    "INSERT INTO estudiantes (carnet, nombre, correo, carrera, estado) VALUES (?, ?, ?, ?, ?)",
                    tuple(estudiante.to_dict().values()),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("El carnet ya está registrado") from error
        return estudiante

    def listar(self):
        with self.connection_factory() as connection:
            rows = connection.execute("SELECT * FROM estudiantes ORDER BY nombre").fetchall()
        return [Estudiante(**dict(row)) for row in rows]

    @staticmethod
    def _required(datos, campo):
        valor = datos.get(campo) if isinstance(datos, dict) else None
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError(f"El campo '{campo}' es obligatorio")
        return valor.strip()