# Asistencia USPG

Aplicación web en Python para gestionar la asistencia universitaria con cuentas de administrador, docente y alumno. El docente abre sesiones de QR temporales; el alumno escanea desde la cámara del navegador de su celular y confirma el registro. El diseño adaptable funciona también desde computadora.

## Requisitos

- Python 3.11 o posterior.
- MySQL 8 o compatible.
- Un navegador moderno. El lector móvil necesita permiso de cámara y un origen seguro: HTTPS o `localhost`.

## Preparación

1. Crea la base de datos en MySQL:

	```sql
	CREATE DATABASE uspg_asistencia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
	```

2. Crea un entorno e instala dependencias:

	```powershell
	py -m venv .venv
	.\.venv\Scripts\Activate.ps1
	pip install -r requirements.txt
	```

3. Copia `.env.example` como `.env` y configura `SECRET_KEY`, `DATABASE_URL`, `ADMIN_EMAIL` y `ADMIN_PASSWORD`. Elige una contraseña no vacía; el formulario da sugerencias de seguridad sin imponer una longitud mínima.

4. Inicializa tablas y cuenta administradora:

	```powershell
	flask --app run.py init-db
	flask --app run.py seed-admin
	```

   Si actualizas una instalación anterior, ejecuta también `flask --app run.py migrate-carnet`. El carnet se solicita para los alumnos nuevos y las cuentas existentes pueden no tenerlo hasta completar la migración institucional.

5. Inicia la aplicación:

	```powershell
	flask --app run.py run --host 0.0.0.0 --port 5000
	```

Entra en `http://localhost:5000`. El administrador crea cuentas de docentes; los estudiantes crean su propia cuenta desde **Crear cuenta** y el sistema solo les asigna el rol de alumno. El carnet debe contener siete dígitos. Los docentes pueden crear sus cursos y abrir sesiones de asistencia.

## Escaneo desde celular

Para que un teléfono alcance al servidor, ambos dispositivos deben estar en la misma red. Configura `APP_BASE_URL` con la dirección local de la computadora, por ejemplo `http://192.168.1.10:5000`, y permite el puerto 5000 en el firewall. Los navegadores móviles suelen exigir HTTPS para habilitar la cámara fuera de `localhost`; en ese caso publica la app detrás de un proxy con TLS. El alumno inicia sesión, toca **Escanear QR**, permite la cámara y confirma el registro.

## Diseño y seguridad

- `app/models.py` define las entidades y restricciones de la base de datos.
- `app/repositories.py` encapsula las consultas y escrituras.
- `app/services.py` implementa reglas de cuentas, cursos y asistencia.
- `app/routes.py` conecta los casos de uso con la interfaz web.
- El administrador puede revisar cuentas, carnets, cursos de cada docente y el historial global de asistencia.
- Los docentes y administradores pueden descargar los registros por curso en CSV o PDF.
- Los QR contienen tokens aleatorios cuya huella se guarda en la base de datos; vencen a los 15 minutos y la restricción única impide duplicados.
- Las contraseñas se guardan con hash, las rutas se protegen por rol y las mutaciones requieren token CSRF.

## Pruebas

```powershell
pytest
```

Las pruebas usan SQLite en memoria y no requieren un servidor MySQL.
