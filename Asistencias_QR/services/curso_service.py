import sqlite3

from models.curso import Curso


class CursoService:
    ESTADOS_VALIDOS = {"activo", "inactivo"}

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def crear(self, datos):
        curso = self._construir_curso(datos)
        try:
            with self.connection_factory() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO cursos (codigo, nombre, seccion, docente, estado)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (curso.codigo, curso.nombre, curso.seccion, curso.docente, curso.estado),
                )
                curso_id = cursor.lastrowid
        except sqlite3.IntegrityError as error:
            raise ValueError("Ya existe un curso con ese código") from error
        return Curso(curso_id, curso.codigo, curso.nombre, curso.seccion, curso.docente, curso.estado)

    def listar(self):
        with self.connection_factory() as connection:
            rows = connection.execute(
                "SELECT id, codigo, nombre, seccion, docente, estado FROM cursos ORDER BY nombre, seccion"
            ).fetchall()
        return [Curso(**dict(row)) for row in rows]

    def actualizar(self, curso_id, datos):
        curso = self._construir_curso(datos, curso_id)
        try:
            with self.connection_factory() as connection:
                cursor = connection.execute(
                    """
                    UPDATE cursos
                    SET codigo = ?, nombre = ?, seccion = ?, docente = ?, estado = ?
                    WHERE id = ?
                    """,
                    (curso.codigo, curso.nombre, curso.seccion, curso.docente, curso.estado, curso_id),
                )
                if cursor.rowcount == 0:
                    raise ValueError("El curso no existe")
                connection.execute(
                    "UPDATE sesiones SET curso = ? WHERE curso_id = ?",
                    (curso.nombre, curso_id),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("Ya existe un curso con ese código") from error
        return curso

    def eliminar(self, curso_id):
        with self.connection_factory() as connection:
            sesiones = connection.execute(
                "SELECT COUNT(*) AS total FROM sesiones WHERE curso_id = ?", (curso_id,)
            ).fetchone()["total"]
            if sesiones:
                raise ValueError("No se puede eliminar un curso que tiene sesiones asociadas")
            cursor = connection.execute("DELETE FROM cursos WHERE id = ?", (curso_id,))
            if cursor.rowcount == 0:
                raise ValueError("El curso no existe")

    def _construir_curso(self, datos, curso_id=None):
        if not isinstance(datos, dict):
            datos = {}
        estado = self._texto(datos, "estado") or "activo"
        if estado not in self.ESTADOS_VALIDOS:
            raise ValueError("El estado debe ser 'activo' o 'inactivo'")
        return Curso(
            id=curso_id,
            codigo=self._requerido(datos, "codigo").upper(),
            nombre=self._requerido(datos, "nombre"),
            seccion=self._texto(datos, "seccion"),
            docente=self._texto(datos, "docente"),
            estado=estado,
        )

    @classmethod
    def _requerido(cls, datos, campo):
        valor = cls._texto(datos, campo)
        if not valor:
            raise ValueError(f"El campo '{campo}' es obligatorio")
        return valor

    @staticmethod
    def _texto(datos, campo):
        valor = datos.get(campo)
        return valor.strip() if isinstance(valor, str) else ""
