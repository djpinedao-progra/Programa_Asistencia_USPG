import argparse, secrets, getpass
from pathlib import Path
from dotenv import load_dotenv
from app import create_app, db
from app.models import User, Course, CourseEnrollment

parser = argparse.ArgumentParser(description="Asistencia USPG")
parser.add_argument("--demo", action="store_true")
parser.add_argument("--port", type=int, default=5000)
args = parser.parse_args()
root = Path(__file__).resolve().parent
load_dotenv(root / ".env")
instance = root / "instance"
instance.mkdir(exist_ok=True)
key = instance / "secret.key"
if not key.exists():
    key.write_text(secrets.token_hex(32))
    key.chmod(0o600)
config = {"SECRET_KEY": key.read_text().strip()}
if args.demo:
    config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + str(instance / "demo.db")
app = create_app(config)
with app.app_context():
    db.create_all()
    if args.demo:
        for name, email, role, carnet in [
            ("Administrador Demo", "admin@administrador.uspg.edu.gt", "admin", None),
            ("Docente Demo", "docente@catedratico.uspg.edu.gt", "docente", None),
            ("Estudiante Demo", "alumno@alumno.uspg.edu.gt", "alumno", "2600001")]:
            if not User.query.filter_by(email=email).first():
                user = User(name=name, email=email, role=role, carnet=carnet)
                user.set_password("Demo-USPG-2026!")
                db.session.add(user)
        db.session.commit()
        teacher = User.query.filter_by(email="docente@catedratico.uspg.edu.gt").first()
        student = User.query.filter_by(email="alumno@alumno.uspg.edu.gt").first()
        if not Course.query.filter_by(code="DEMO-101").first():
            course = Course(name="Programación II", code="DEMO-101", teacher_id=teacher.id,
                            schedule="Sábado 08:00–10:00", classroom="Laboratorio 1")
            db.session.add(course)
            db.session.flush()
            db.session.add(CourseEnrollment(course_id=course.id, student_id=student.id))
            db.session.commit()
        print("DEMO: admin@administrador.uspg.edu.gt / docente@catedratico.uspg.edu.gt / alumno@alumno.uspg.edu.gt")
        print("Contraseña demo: Demo-USPG-2026!")
    elif not User.query.filter_by(role="admin").first():
        print("Crea tu primera cuenta administradora.")
        email=input("Correo: ").strip()
        name=input("Nombre: ").strip()
        password=getpass.getpass("Contraseña: ")
        from app.services import UserService
        if UserService.email_role(email) != "admin" or not name or len(password)<8:
            raise SystemExit("Ingresa nombre, correo válido y contraseña de al menos 8 caracteres.")
        user=User(name=name,email=email,role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
print(f"Abre http://127.0.0.1:{args.port} · Ctrl+C para detener")
app.run(host="127.0.0.1",port=args.port,debug=False)
