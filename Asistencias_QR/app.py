import os

from flask import Flask, render_template
from database.schema import init_db
from controllers.estudiante_controller import estudiante_bp
from controllers.sesion_controller import sesion_bp
from controllers.asistencia_controller import asistencia_bp
from controllers.google_controller import google_bp

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "clave-local-desarrollo")
init_db()

# Registrar controladores
app.register_blueprint(estudiante_bp)
app.register_blueprint(sesion_bp)
app.register_blueprint(asistencia_bp)
app.register_blueprint(google_bp)


@app.get("/")
def inicio():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
