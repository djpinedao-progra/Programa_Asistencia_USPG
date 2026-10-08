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

3. Copia `.env.example` como `.env` y configura `SECRET_KEY`, `DATABASE_URL`, `ADMIN_EMAIL` (un correo `@administrador.uspg.edu.gt`) y `ADMIN_PASSWORD`. `APP_TIMEZONE` define la zona horaria que se presenta en pantalla (por defecto `America/Guatemala`); las fechas se almacenan en UTC. Elige una contraseña no vacía; el formulario da sugerencias de seguridad sin imponer una longitud mínima.

4. Inicializa tablas y cuenta administradora:

	```powershell
	flask --app run.py init-db
	flask --app run.py seed-admin
	```

	Para que todo el equipo tenga las mismas cuentas de prueba, ejecuta también:

	```powershell
	flask --app run.py seed-test-users
	```

	| Rol | Nombre | Usuario | Carnet | Contraseña |
	| --- | --- | --- | --- | --- |
	| Administrador | Administrador Demo | admin@administrador.uspg.edu.gt | — | 123 |
	| Docente | Carlos Méndez | docente@catedratico.uspg.edu.gt | — | 123 |
	| Alumno | Ana López | alumno1@alumno.uspg.edu.gt | 2600010 | 123 |
	| Alumno | Luis Pérez | alumno2@alumno.uspg.edu.gt | 2600011 | 123 |
	| Alumno | María García | alumno3@alumno.uspg.edu.gt | 2600012 | 123 |
	| Alumno | Carlos Morales | alumno4@alumno.uspg.edu.gt | 2600013 | 123 |
	| Alumno | José Hernández | alumno5@alumno.uspg.edu.gt | 2600014 | 123 |
	| Alumno | Sofía Castillo | alumno6@alumno.uspg.edu.gt | 2600015 | 123 |

	También crea los cursos ING-220, ING-221 e ING-222 con Carlos Méndez como docente, los seis alumnos matriculados y diez sesiones de asistencia por curso. El comando crea lo que falte y vuelve a poner la contraseña `123` en las cuentas que ya existan; no duplica cursos. Si tu base tiene las cuentas anteriores `@uspg.edu`, las renombra al dominio nuevo conservando sus cursos y asistencias. Los datos son solo para desarrollo: no lo ejecutes en un servidor público.

	Si actualizas una instalación anterior, ejecuta `flask --app run.py migrate-carnet`, `flask --app run.py migrate-teacher-tools`, `flask --app run.py migrate-audit-log` y `flask --app run.py migrate-expo`. Estas migraciones agregan campos y tablas sin eliminar los cursos o asistencias guardados. El carnet se solicita para los alumnos nuevos y las cuentas existentes pueden no tenerlo hasta completar la migración institucional.

5. Inicia la aplicación:

	```powershell
	flask --app run.py run --host 0.0.0.0 --port 5000
	```

Entra en `http://localhost:5000`. El administrador crea cuentas de docentes, da de alta los cursos y asigna docente, horario, modalidad, salón y estudiantes. Los estudiantes crean su propia cuenta desde **Crear cuenta** y el sistema solo les asigna el rol de alumno. El carnet debe contener siete dígitos. El docente gestiona sus cursos asignados, toma asistencia por QR o manualmente, cierra sesiones y consulta los avisos e historiales.

## Cuentas y correos institucionales

El dominio del correo define el rol de cada cuenta y se valida al crearla, al editarla y al iniciar sesión:

| Rol | Dominio |
| --- | --- |
| Administrador | `@administrador.uspg.edu.gt` |
| Docente | `@catedratico.uspg.edu.gt` |
| Alumno | `@alumno.uspg.edu.gt` |

Una cuenta cuyo correo no corresponde a su rol no puede iniciar sesión, y si su correo cambia mientras está conectada la sesión se cierra.

## Recuperar contraseña

El enlace **¿Olvidaste tu contraseña?** envía por correo una contraseña temporal válida por 15 minutos que solo se activa al iniciar sesión con ella; mientras tanto la contraseña actual sigue funcionando. Se guarda solo como hash, admite una solicitud cada dos minutos por cuenta y la página responde lo mismo exista o no la cuenta. Requiere configurar `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_USERNAME` y `SMTP_PASSWORD` (STARTTLS, o `SMTP_SSL=true` para TLS directo); sin servidor de correo no se envía nada y la contraseña no cambia.

## Expo San Pablo

Formulario público en `/expo-san-pablo` para registrar la asistencia a la Expo sin cuenta: nombre, correo de cualquier proveedor, categoría (estudiante, catedrático o público general), participación, opinión opcional y consentimiento. Se cuenta un registro por correo. El administrador ve en **Expo San Pablo** los totales por categoría, el detalle con filtro, descarga PDF o Excel y un QR fijo que apunta al formulario usando `APP_BASE_URL`; si cambia la dirección del programa hay que imprimir el QR de nuevo. En instalaciones existentes ejecuta `flask --app run.py migrate-expo`.

## Publicación (Render)

`render.yaml` define un servicio web con gunicorn y una base PostgreSQL. Revisa el costo de los planes antes de crearlos. Al publicar, `prepare_production.py` crea las tablas y la primera cuenta administradora con `ADMIN_EMAIL` y `ADMIN_PASSWORD`, sin cuentas de prueba. Con `APP_ENV=production` el programa exige `SECRET_KEY` y `DATABASE_URL`, y envía la cookie de sesión solo por HTTPS. Guarda las credenciales en las variables privadas del alojamiento, nunca en GitHub.

## Escaneo desde celular

Para que un teléfono alcance al servidor, ambos dispositivos deben estar en la misma red. Configura `APP_BASE_URL` con la dirección pública segura de la aplicación y publícala detrás de un proxy con TLS; los navegadores móviles exigen HTTPS para solicitar permiso y habilitar la cámara. La dirección HTTP de la computadora en la red local no permite escanear desde la mayoría de los teléfonos. El alumno inicia sesión, toca **Escanear QR**, acepta el permiso de cámara del navegador y confirma el registro.

## Diseño y seguridad

- `app/models.py` define las entidades y restricciones de la base de datos.
- `app/repositories.py` encapsula las consultas y escrituras.
- `app/services.py` implementa reglas de cuentas, cursos y asistencia.
- `app/routes.py` conecta los casos de uso con la interfaz web.
- El administrador puede revisar cuentas, carnets, cursos de cada docente y el historial global de asistencia.
- El panel administrador incluye apartados separados para estudiantes, docentes, cursos, asistencias, reportes e historial; permite editar perfiles, habilitar cursos y filtrar registros.
- La administración permite importar matrículas desde CSV con las columnas `course_code,carnet`; se muestra una vista previa y las filas inválidas antes de confirmar.
- Los historiales de alumno, docente y administración se muestran en páginas de 25 registros y conservan los filtros seleccionados.
- Cada usuario puede cambiar su contraseña desde **Seguridad**; un administrador puede restablecer la de estudiantes o docentes desde su perfil.
- Los reportes administrativos muestran porcentajes y niveles de riesgo, con exportación PDF global, por curso o por sesión.
- Los docentes y administradores pueden descargar los registros por curso en CSV o PDF.
- Los QR contienen tokens aleatorios cuya huella se guarda en la base de datos; vencen a los 5 minutos, pueden renovarse desde la sesión y la restricción única impide duplicados. Solo los alumnos inscritos en el curso pueden registrar asistencia.
- El panel docente recuerda el último curso usado y preselecciona un curso si su día y hora coinciden con el horario actual del navegador.
- La sesión docente indica cuándo se actualizó la lista de asistencia y permite solicitar una actualización manual.
- La sección **Auditoría** registra correcciones de asistencia, cambios de perfil, matrículas y operaciones administrativas, con actor y fecha.
- `backup-db` crea respaldos comprimidos y versionados; `restore-db` valida formato y esquema antes de reemplazar los datos dentro de una transacción.
- Al cerrar una sesión, los estudiantes asignados sin registro quedan como ausentes. Cada registro conserva estado (presente, ausente o justificado), hora y origen (QR o docente). Las correcciones guardan su propia hora sin cambiar la del registro original, y las faltas justificadas se cuentan aparte de las faltas.
- Los avisos docentes quedan en el historial y aparecen en el panel del estudiante; los avisos preventivos se generan bajo 90% de asistencia y el mínimo de referencia para examen final es 80%.
- Las contraseñas se guardan con hash, las rutas se protegen por rol y las mutaciones requieren token CSRF.

## Respaldos

Ejecuta los comandos desde una instalación con el esquema inicializado. La restauración reemplaza todas las filas y exige confirmación explícita:

```powershell
flask --app run.py backup-db instance/asistencia-backup.json.gz
flask --app run.py restore-db instance/asistencia-backup.json.gz --yes
```

El respaldo contiene información personal y hashes de contraseñas. Guárdalo en un medio con acceso restringido, protégelo con cifrado del sistema o del almacenamiento y no lo compartas ni lo publiques. La restauración requiere un esquema compatible; en una base nueva, ejecuta primero las migraciones.

## Pruebas

```powershell
pytest
```

Las pruebas usan SQLite en memoria y no requieren un servidor MySQL.

Las pruebas de navegador usan Playwright y Chromium opcionales:

```powershell
py -m pip install -r requirements-browser.txt
py -m playwright install chromium
py -m pytest tests/test_browser.py -q
```
