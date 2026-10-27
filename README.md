# USPG · Nuevo proyecto independiente
Basado en el motor de Programa_Asistencia_USPG, commit 9464e9973572dc8b0c848a5248aff84a406696f6.
Conserva licencia GPL-3.0: ver LICENSE. Reutiliza la lógica existente; no es una reescritura desde cero.

## Mac: abrir esta carpeta en Visual Studio Code
```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python iniciar.py --demo
```
## Windows PowerShell
```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python iniciar.py --demo
```
Abre http://127.0.0.1:5000
Cuentas demo: admin@administrador.uspg.edu.gt / docente@catedratico.uspg.edu.gt / alumno@alumno.uspg.edu.gt
Contraseña común: Demo-USPG-2026!
El modo demo usa una base separada y crea un curso con docente y alumno.
No contiene asistencias inventadas: registra las tuyas al probar.

## Instalación propia
Ejecuta python iniciar.py sin --demo. Se crea una base SQLite y se solicita
la primera cuenta administradora. No copies instance del proyecto anterior.
Puerto alternativo: python iniciar.py --demo --port 5001.
Para permitir acceso desde otros dispositivos de la misma red Wi-Fi, inicia con
`python iniciar.py --demo --host 0.0.0.0` y abre `http://<IP-LAN-del-equipo>:5000`.
El modo de escucha predeterminado sigue siendo solo local. El servidor de
desarrollo no debe exponerse directamente a internet; las cuentas demo usan
credenciales compartidas.
DATABASE_URL permite usar MySQL si lo configuras en .env.

## Funciones
Administrador: estudiantes, docentes, cursos, matrículas CSV, asistencia, reportes PDF y auditoría.
Docente: sesiones QR temporales, registro manual, cursos, avisos y exportaciones.
Alumno: registro con carnet, historial y escaneo QR.
Contraseñas con hash, permisos por rol, CSRF y cambio de contraseña.

Las sesiones de asistencia se cierran automáticamente al finalizar el horario
del curso más 30 minutos de gracia. El margen puede cambiarse con
`ATTENDANCE_CLOSE_GRACE_MINUTES`; si el horario no coincide con el día de
apertura, el margen se cuenta desde la apertura.

## Organización MVC
El código se divide en controladores HTTP (`app/controllers/`), servicios de
negocio (`app/services/`), repositorios de datos (`app/repositories/`), modelos
(`app/models/`) y vistas (`app/views/`, que incluye plantillas, estáticos y
generadores de reportes). La guía para ubicar cambios es
[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md); los aspectos aún pendientes de la
migración se documentan en [docs/PENDIENTES.md](docs/PENDIENTES.md).

Diseño rojo, dorado y azul oscuro. Rethink Sans, utilizada en la web de la universidad.
Logo original descargado sin editar de la web oficial: https://uspg.edu.gt/site/wp-content/uploads/2026/07/LOGO-EDITABLE-USPG-1.png
Paleta: azul #011931, rojo #AA182B y blanco.

El servidor local abre solo en tu computadora por defecto. Cámara móvil requiere HTTPS.
Google Fonts necesita internet; sin conexión usa fuente del sistema.
Pruebas: python -m pytest -q.
Pruebas de navegador: Playwright con Chromium.

## IntegraciÃ³n opcional con Google Classroom

La integraciÃ³n se mantiene oculta por defecto. Al establecer
`GOOGLE_CLASSROOM_ENABLED=true`, el administrador puede conectar una cuenta de
Google mediante OAuth e importar cursos activos, docentes y alumnos. Classroom
no proporciona un horario semanal estructurado, salÃ³n normalizado ni carnet;
estos datos se confirman antes de importar.

Permisos solicitados: cursos, matrÃ­culas y correos en modo de solo lectura. Los
tokens OAuth se cifran antes de guardarse. Configura `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET` y `GOOGLE_TOKEN_ENCRYPTION_KEY` como secretos del
entorno. `GOOGLE_REDIRECT_URI` puede omitirse en Render porque se deriva de
`RENDER_EXTERNAL_URL`; localmente debe apuntar a `/admin/google/callback`.

`render.staging.yaml` define un servicio independiente
para probar la rama `codex/google-classroom-integration` sin tocar producciÃ³n.

Para evitar el costo de una segunda base PostgreSQL, reutiliza la instancia
existente con `DB_SCHEMA=classroom_pruebas`; las tablas de prueba quedan en ese
esquema y no modifican las tablas de producción. `DATABASE_URL` se copia como
secreto desde el servicio principal.

Motor original: https://github.com/djpinedao-progra/Programa_Asistencia_USPG

## Despliegue temporal gratuito en Render

El archivo `render.yaml` crea un Web Service y una base PostgreSQL gratuitos
en la misma región. En Render selecciona **New > Blueprint**, conecta este
repositorio y usa la rama `main`. Durante la creación, Render solicitará:

- `ADMIN_EMAIL`: un correo terminado en `@administrador.uspg.edu.gt`.
- `ADMIN_PASSWORD`: una contraseña nueva y segura para producción.

`SECRET_KEY` y `DATABASE_URL` se configuran automáticamente. En cada arranque,
`prepare_production.py` crea las tablas que falten y solamente crea la cuenta
administradora cuando todavía no existe ninguna. No se crean usuarios demo.

El plan gratuito es apropiado para la prueba de 15 días: puede tardar cerca de
un minuto en despertar después de un período sin tráfico. La recuperación por
correo no está habilitada porque Render Free bloquea los puertos SMTP comunes.


## Rama Luis independiente

Consulta [LUIS-INDEPENDIENTE.md](LUIS-INDEPENDIENTE.md) para iniciar en una carpeta nueva y configurar una base propia. La Expo permite registro sin iniciar sesión y reportes administrativos; consulta [EXPO-SAN-PABLO.md](EXPO-SAN-PABLO.md).
