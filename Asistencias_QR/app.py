from flask import Flask
from database.schema import init_db
from controllers.estudiante_controller import estudiante_bp
from controllers.sesion_controller import sesion_bp
from controllers.asistencia_controller import asistencia_bp

app = Flask(__name__)
init_db()

# Registrar controladores
app.register_blueprint(estudiante_bp)
app.register_blueprint(sesion_bp)
app.register_blueprint(asistencia_bp)

if __name__ == "__main__":
    app.run(debug=True)
