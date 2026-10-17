import argparse, secrets, getpass
from pathlib import Path
from dotenv import load_dotenv
from app import create_app, db
from app.models import User
from app.services.seed_service import seed_demo_data

parser = argparse.ArgumentParser(description="Asistencia USPG")
parser.add_argument("--demo", action="store_true")
parser.add_argument("--port", type=int, default=5000)
parser.add_argument(
    "--host",
    default="127.0.0.1",
    help="Dirección de escucha (usa 0.0.0.0 para permitir acceso desde la red local)",
)
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
        seed_demo_data()
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
if args.host == "0.0.0.0":
    print(f"Para otros dispositivos de tu red local, usa http://<IP-LAN>:{args.port}")
app.run(host=args.host, port=args.port, debug=False)
