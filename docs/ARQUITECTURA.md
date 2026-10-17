# Arquitectura MVC

La aplicación está organizada por responsabilidades para localizar un cambio sin
tener que recorrer todas las rutas. La fábrica está en `app/__init__.py` y la
configuración de entorno en `app/config.py`.

## Carpetas

```text
app/
├── __init__.py, config.py, extensions.py, security.py, cli.py
├── models/          # Tablas SQLAlchemy, relaciones y métodos del registro
├── repositories/    # Consultas y persistencia por entidad y reportes agregados
├── services/        # Reglas, validaciones, métricas y preparación de datos
├── controllers/     # Blueprints y rutas HTTP agrupadas por área
├── views/
│   ├── templates/   # Plantillas Jinja por pantalla y rol
│   ├── static/      # css/, js/ e img/
│   └── reports/     # Generadores de bytes PDF, CSV, Excel y QR
└── utils/           # Funciones compartidas, como conversión de fechas
```

## Dependencias

El flujo previsto es `controllers → services → repositories → models`.
Los controladores interpretan HTTP y preparan respuestas; los servicios aplican
reglas sin depender de Flask; los repositorios encapsulan SQLAlchemy. Los
generadores de `views/reports/` reciben estructuras de datos y devuelven bytes.
Las plantillas reciben datos preparados y no consultan la base de datos.

El código de controladores y servicios no consulta directamente la sesión de
SQLAlchemy. Las consultas de métricas que combinan asistencia y matrícula están
en `AttendanceMetricsRepository`; el respaldo usa `BackupRepository`. Algunos
handlers aún requieren reducir su preparación de datos, como se detalla en
[PENDIENTES.md](PENDIENTES.md).

## Recorrido de una petición

Cuando un alumno confirma un QR, `controllers/student_controller.py` registra
`POST /api/asistencia` en `record_attendance`. El controlador entrega el token y
el usuario a `AttendanceService.record_attendance`; el servicio verifica el
token, la vigencia, la matrícula y el rol mediante `AttendanceRepository`, que
busca la sesión y la matrícula y persiste `Attendance`. El controlador convierte
el resultado o el error de validación en un mensaje y una redirección.

## ¿Quiero cambiar X? → ¿Dónde?

| Cambio | Ubicación |
|---|---|
| Cambiar un texto o estructura de pantalla | `app/views/templates/` |
| Cambiar colores, espaciado o tipografía | `app/views/static/css/` |
| Cambiar una interacción de pantalla | `app/views/static/js/` |
| Cambiar una regla de usuario, curso o asistencia | `app/services/` |
| Cambiar una consulta a la base | `app/repositories/` |
| Agregar o cambiar una columna | `app/models/` y la migración correspondiente en `app/cli.py` |
| Cambiar la duración configurada del QR | `app/config.py` y `AttendanceService`; revisar el límite actual documentado en `PENDIENTES.md` |
| Agregar un PDF, Excel, CSV o QR | `app/views/reports/` y la ruta/controlador que lo entrega |
| Agregar una URL | Un módulo en `app/controllers/` y su importación en `register_controllers()` |
| Cambiar una variable de entorno | `app/config.py` |
| Cambiar recuperación, respaldo o semilla demo | Servicio del dominio en `app/services/` y su comando/arranque asociado |

Los blueprints `main` y `expo` conservan los nombres públicos usados por
`url_for`. Los endpoints se agrupan por área en los controladores; el inventario
de rutas se conserva en `docs/endpoints_antes.txt`.
