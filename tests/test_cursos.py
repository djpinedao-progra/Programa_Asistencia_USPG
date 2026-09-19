import sqlite3
import sys
import tempfile
import unittest
import gc
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1] / "Asistencias_QR"
sys.path.insert(0, str(PROJECT_DIR))


class CursoApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.database_path = Path(cls.temp_dir.name) / "test.db"

        # Simula una base creada por la versión anterior, sin curso_id.
        connection = sqlite3.connect(cls.database_path)
        try:
            connection.execute(
                """
                CREATE TABLE sesiones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    curso TEXT NOT NULL,
                    fecha_hora TEXT NOT NULL,
                    token_qr TEXT NOT NULL UNIQUE
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

        from database import conexion

        conexion.DATABASE_PATH = cls.database_path
        from database.schema import init_db
        from flask import Flask
        from controllers.curso_controller import curso_bp

        init_db()
        app = Flask(__name__)
        app.register_blueprint(curso_bp)
        app.config.update(TESTING=True)
        cls.client = app.test_client()
        cls.get_connection = staticmethod(conexion.get_connection)

    @classmethod
    def tearDownClass(cls):
        gc.collect()
        cls.temp_dir.cleanup()

    def setUp(self):
        with self.get_connection() as connection:
            connection.execute("DELETE FROM asistencias")
            connection.execute("DELETE FROM sesiones")
            connection.execute("DELETE FROM cursos")

    def test_migra_la_tabla_de_sesiones(self):
        with self.get_connection() as connection:
            columnas = {
                row["name"] for row in connection.execute("PRAGMA table_info(sesiones)")
            }
        self.assertIn("curso_id", columnas)

    def test_crud_de_cursos(self):
        respuesta = self.client.post(
            "/api/cursos",
            json={
                "codigo": "bd-101",
                "nombre": "Bases de datos I",
                "seccion": "A",
                "docente": "Ana Martínez",
            },
        )
        self.assertEqual(201, respuesta.status_code)
        curso = respuesta.get_json()["data"]
        self.assertEqual("BD-101", curso["codigo"])

        duplicado = self.client.post(
            "/api/cursos", json={"codigo": "BD-101", "nombre": "Otro"}
        )
        self.assertEqual(400, duplicado.status_code)

        listado = self.client.get("/api/cursos").get_json()["data"]
        self.assertEqual(1, len(listado))

        actualizado = self.client.put(
            f"/api/cursos/{curso['id']}",
            json={
                "codigo": "BD-102",
                "nombre": "Bases de datos II",
                "seccion": "B",
                "docente": "Ana Martínez",
                "estado": "inactivo",
            },
        )
        self.assertEqual(200, actualizado.status_code)
        self.assertEqual("inactivo", actualizado.get_json()["data"]["estado"])

        eliminado = self.client.delete(f"/api/cursos/{curso['id']}")
        self.assertEqual(200, eliminado.status_code)
        self.assertEqual([], self.client.get("/api/cursos").get_json()["data"])

    def test_no_elimina_un_curso_con_sesiones(self):
        curso = self.client.post(
            "/api/cursos", json={"codigo": "PRO-101", "nombre": "Programación I"}
        ).get_json()["data"]
        with self.get_connection() as connection:
            connection.execute(
                """
                INSERT INTO sesiones (curso, curso_id, fecha_hora, token_qr)
                VALUES (?, ?, ?, ?)
                """,
                (curso["nombre"], curso["id"], "2026-09-19T10:00:00", "token-prueba"),
            )

        respuesta = self.client.delete(f"/api/cursos/{curso['id']}")
        self.assertEqual(400, respuesta.status_code)
        self.assertIn("sesiones asociadas", respuesta.get_json()["message"])

    def test_crea_sesion_con_curso_activo(self):
        curso = self.client.post(
            "/api/cursos", json={"codigo": "WEB-101", "nombre": "Desarrollo web"}
        ).get_json()["data"]
        from services.sesion_service import SesionService

        qr_directory = Path(self.temp_dir.name) / "qr"
        service = SesionService(self.get_connection, qr_directory)
        sesion = service.crear(curso_id=curso["id"])

        self.assertEqual(curso["id"], sesion.curso_id)
        self.assertEqual("Desarrollo web", sesion.curso)
        self.assertTrue((qr_directory / f"sesion_{sesion.id}.png").exists())

        self.client.put(
            f"/api/cursos/{curso['id']}",
            json={"codigo": "WEB-101", "nombre": "Desarrollo web", "estado": "inactivo"},
        )
        with self.assertRaisesRegex(ValueError, "curso inactivo"):
            service.crear(curso_id=curso["id"])


if __name__ == "__main__":
    unittest.main()
